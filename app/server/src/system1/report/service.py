import asyncio
import json
import statistics
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from system1.adapters.eval_files import EvalFilesSource
from system1.agent.context import AgentContext, register_action_handler
from system1.agent.models import PendingAction
from system1.auth.principal import Principal
from system1.config import Settings
from system1.contracts.training import EvalAnswer, TrainingJob
from system1.datasets import service as dataset_service
from system1.datasets.constants import MIN_PER_BUCKET, VERDICT_MIN_TEST_PER_BUCKET
from system1.datasets.service import NewExample
from system1.decisions.models import Decision, Feedback
from system1.domain.policy import Policy, validate_policy
from system1.domain.questions import build_questions
from system1.errors import ApiError
from system1.generation.service import BucketsUnfinished
from system1.jobs import service as job_service
from system1.jobs.models import Job
from system1.jobs.service import JobContext
from system1.projects import service as project_service
from system1.projects.models import Project
from system1.providers import Providers
from system1.report.evaluation import PredRecord, evaluate_jev, evaluate_lane, load_examples, load_test_examples
from system1.report.models import ReportCard
from system1.report.schemas import Confusion, Report, ReportDetails, ReportRow, RowKey, Verdict
from system1.report.stats import accuracy_ci, paired_diff_ci, per_bucket_accuracy, top_confusions
from system1.templates.catalog import get_template

# How often the job asks the trainer how it is getting on. Tests set it to 0.
POLL_INTERVAL_S = 0.25
# Above this share of failed answers a row isn't scored: the accuracy would mostly measure the outage.
ERROR_LIMIT = 0.30
PREVIEW_MESSAGE = "Real training connects soon."
NOT_CONNECTED_MESSAGE = "Trained, but your model isn't connected yet."
NO_ANSWER = "no answer"

LABELS: dict[RowKey, str] = {
    "sys1": "Your model",
    "jev": "Jev with your guidelines",
    "jev_labels": "Jev with buckets only",
    "base": "Untrained base model",
}
ROW_ORDER: tuple[RowKey, ...] = ("sys1", "jev", "jev_labels", "base")
# How far through its own work the trainer is at each stage it reports.
STAGE_PROGRESS = {"preparing": 0.1, "learning": 0.4, "checking": 0.7, "testing": 0.9}
TRAINER_SHARE = 0.85  # the rest of the job's progress is the Jev scoring


class TrainingNotReady(ApiError):
    status_code = 422
    code = "training_not_ready"
    message = "This project isn't ready to train yet."


class TrainingRunning(ApiError):
    status_code = 409
    code = "training_running"
    message = "A training run is already going for this project."


class TrainerFailed(ApiError):
    status_code = 502
    code = "training_failed"
    message = "Training didn't finish."


def _serves(provider: object | None, adapter_ref: str) -> bool:
    """True when the sys1 provider says it serves exactly this adapter."""
    return provider is not None and getattr(provider, "adapter_ref", None) == adapter_ref


def _names(policy: Policy, keys: Sequence[str]) -> str:
    by_key = {o.key: o.name for o in policy.options}
    return ", ".join(by_key.get(k, k) for k in keys)


def _pct(value: float | None) -> str:
    return f"{round((value or 0) * 100)}%"


# ---- scoring a card ----------------------------------------------------------------------------------------------


def scored_row(key: RowKey, records: list[PredRecord], subject: str) -> ReportRow:
    n = len(records)
    errors = sum(r.error is not None for r in records)
    row = ReportRow(key=key, label=LABELS[key], status="ok", n=n, errors=errors)
    if errors:
        row.message = f"{subject} errored on {errors} of {n}"
    if n == 0:
        return row.model_copy(update={"status": "unavailable", "message": "There are no test examples to score."})
    if errors / n > ERROR_LIMIT:
        return row.model_copy(update={"status": "errored"})
    accuracy, low, high = accuracy_ci([r.correct for r in records])
    latencies = [r.latency_ms for r in records if r.latency_ms is not None]
    row.accuracy, row.ci_low, row.ci_high = accuracy, low, high
    row.median_latency_ms = statistics.median(latencies) if latencies else None
    return row


def _details(
    records_by_key: dict[RowKey, list[PredRecord]], rows: list[ReportRow], buckets: dict[str, int]
) -> ReportDetails:
    details = ReportDetails(test_per_bucket=buckets)
    for row in rows:
        if row.status != "ok":
            continue
        records = records_by_key[row.key]
        golds = [r.gold for r in records]
        preds = [r.pred or NO_ANSWER for r in records]
        details.per_bucket[row.key] = per_bucket_accuracy(golds, preds)
        details.confusions[row.key] = [Confusion(gold=g, pred=p, count=n) for g, p, n in top_confusions(golds, preds)]
    return details


def too_few(test_per_bucket: dict[str, int]) -> bool:
    if not test_per_bucket:
        return True
    return sum(test_per_bucket.values()) / len(test_per_bucket) < VERDICT_MIN_TEST_PER_BUCKET


def _verdict(
    rows: dict[RowKey, ReportRow], records: dict[RowKey, list[PredRecord]], few: bool, preview: bool
) -> Verdict:
    sys1, jev, labels = rows.get("sys1"), rows.get("jev"), rows.get("jev_labels")
    jev_errored = any(r.status == "errored" for r in (jev, labels) if r)
    if sys1 is None or sys1.accuracy is None:
        # Nothing to compare yet, however many test examples there are: say so before anything about getting more.
        lead = (
            "Real training connects soon, so there's no verdict on your model yet."
            if preview
            else "There's no verdict on your model yet."
        )
        scores = [f"{r.label} gets {_pct(r.accuracy)}" for r in (jev, labels) if r and r.accuracy is not None]
        if jev_errored:
            tail = "Jev didn't answer enough of your test examples to show how it does. Try again in a minute."
        elif scores:
            tail = f"Here's how Jev does on your test examples: {'; '.join(scores)} right."
        else:
            tail = ""
        return Verdict(winner="none", sentence=f"{lead} {tail}".strip())
    if jev_errored or jev is None or jev.accuracy is None:
        return Verdict(
            winner="none",
            sentence="Jev didn't answer enough of your test examples, so there's no verdict. Try again in a minute.",
        )
    if few:
        return Verdict(
            winner="none",
            sentence=(
                "Too few test examples for a firm verdict. "
                f"Add more examples so each bucket has about {VERDICT_MIN_TEST_PER_BUCKET} to test on."
            ),
        )

    mine = {r.id: r.correct for r in records["sys1"]}
    theirs = {r.id: r.correct for r in records["jev"]}
    ids = [i for i in mine if i in theirs]
    diff, low, high = paired_diff_ci([mine[i] for i in ids], [theirs[i] for i in ids])
    if low > 0:
        winner: Verdict = Verdict(
            winner="sys1",
            sentence=(
                f"Your model got {_pct(sys1.accuracy)} of your test examples right, "
                f"ahead of Jev with your guidelines at {_pct(jev.accuracy)}."
            ),
        )
    elif high < 0:
        winner = Verdict(
            winner="jev",
            sentence=(
                f"Jev with your guidelines got {_pct(jev.accuracy)} right, ahead of your model at {_pct(sys1.accuracy)}. "
                "More examples, or clearer guidelines, are the next step."
            ),
        )
    else:
        winner = Verdict(
            winner="inconclusive",
            sentence=(
                f"Your model ({_pct(sys1.accuracy)}) and Jev with your guidelines ({_pct(jev.accuracy)}) "
                "are too close to call on these test examples."
            ),
        )
    winner.diff, winner.ci_low, winner.ci_high = diff, low, high
    return winner


def assemble(
    records: dict[RowKey, list[PredRecord]],
    sys1_note: ReportRow | None,
    test_per_bucket: dict[str, int],
    *,
    preview: bool = False,
    skip_few_check: bool = False,
) -> tuple[list[ReportRow], Verdict, ReportDetails]:
    """Rows in card order, the verdict and the details. `sys1_note` stands in for your model's row when it has no records."""
    subjects: dict[RowKey, str] = {"sys1": "Your model", "jev": "Jev", "jev_labels": "Jev", "base": "The base model"}
    by_key: dict[RowKey, ReportRow] = {k: scored_row(k, r, subjects[k]) for k, r in records.items()}
    if sys1_note is not None and "sys1" not in records:
        by_key["sys1"] = sys1_note
    rows = [by_key[k] for k in ROW_ORDER if k in by_key]
    verdict = _verdict(by_key, records, few=not skip_few_check and too_few(test_per_bucket), preview=preview)
    return rows, verdict, _details(records, rows, test_per_bucket)


# ---- carrying live corrections into the examples ---------------------------------------------------------------


def _carry_feedback(session: Session, project: Project, policy: Policy) -> tuple[int, int]:
    """Copies corrections that may be trained on into the examples. Returns (copied, skipped because the bucket is gone).
    Leaves the transaction to the caller."""
    keys = {o.key for o in policy.options}
    pending = session.execute(
        select(Feedback, Decision)
        .join(Decision, Decision.id == Feedback.decision_id)
        .where(
            Feedback.project_id == project.id,
            Feedback.training_eligible.is_(True),
            Feedback.copied_to_example.is_(False),
        )
        .order_by(Feedback.created_at, Feedback.id)
    ).all()
    rows, stale = [], 0
    for feedback, decision in pending:
        if feedback.correct_label not in keys:
            stale += 1
            continue
        state = decision.state_json
        rows.append(
            NewExample(
                state if isinstance(state, str | dict) else json.dumps(state), feedback.correct_label, "corrected"
            )
        )
        feedback.copied_to_example = True
    copied = dataset_service.add_examples(session, project, rows, commit=False) if rows else 0
    return copied, stale


# ---- starting a training run ------------------------------------------------------------------------------------


def _check_ready(session: Session, project: Project, policy: Policy) -> None:
    if validate_policy(policy):
        raise BucketsUnfinished("Finish your buckets before training.")
    running = session.scalar(
        select(func.count())
        .select_from(Job)
        .where(Job.project_id == project.id, Job.kind == "training", Job.status.in_(("queued", "running")))
    )
    if running:
        raise TrainingRunning()
    health = dataset_service.health(session, project)
    if health.below_minimum:
        raise TrainingNotReady(f"Add at least {MIN_PER_BUCKET} examples to: {_names(policy, health.below_minimum)}.")
    if project.frozen_at is not None:
        # Before the first training the freeze gives every bucket that has the minimum some test examples; afterwards
        # a bucket can lose them only by relabelling, and the test set never moves.
        empty = [k for k, c in health.per_bucket.items() if c["test"] == 0 and k in {o.key for o in policy.options}]
        if empty:
            raise TrainingNotReady(
                f"These buckets have no test examples to check your model on: {_names(policy, empty)}."
            )


def start_training(
    session: Session, providers: Providers, settings: Settings, principal: Principal, project: Project
) -> str:
    """Starts the job and returns its id. Call it from the event loop thread (an async route or handler)."""
    project_service.get_project(session, principal, project.id)
    policy, policy_version = project_service.latest_policy(session, project)
    _check_ready(session, project, policy)

    # Freeze first, so the corrections copied next can only land in train or calibration.
    dataset_service.freeze(session, project)
    copied, stale = _carry_feedback(session, project, policy)
    job = job_service.create_job(session, principal, project.id, "training")

    project_id, org_id = project.id, principal.org_id
    test_set_version, dataset_version = project.test_set_version, project.dataset_version
    dataset_ref = f"project:{project_id}:v{dataset_version}"
    config: dict = {"project_id": project_id, "test_set_version": test_set_version}
    if getattr(providers.trainer, "needs_examples", False):
        config["questions"] = build_questions(policy, "labels")
        config["examples"] = [
            {"id": e.id, "split": e.split, "input": e.input, "label": e.label} for e in load_examples(session, project)
        ]
    summary: dict = {"copied": copied, "skipped_stale": stale}

    async def work(ctx: JobContext) -> dict:
        ctx.result = dict(summary)
        own = ctx.session.get(Project, project_id)
        if own is None:  # deleted while it ran
            return ctx.result
        progress = _Progress(ctx)
        evaluation = asyncio.create_task(
            evaluate_jev(
                ctx.session,
                providers,
                own,
                test_set_version,
                policy_and_version=(policy, policy_version),
                on_progress=progress.scored,
            )
        )
        try:
            trained = await _run_trainer(providers, dataset_ref, config, progress)
            if trained.status == "failed":
                raise TrainerFailed(trained.message)
        except BaseException:
            evaluation.cancel()
            await asyncio.gather(evaluation, return_exceptions=True)
            raise
        jev = await evaluation

        records: dict[RowKey, list[PredRecord]] = {"jev": jev["jev"]}
        sys1_note: ReportRow | None = None
        scored_remotely = trained.status == "succeeded" and "sys1" in trained.evaluations
        if scored_remotely:
            records["sys1"] = _records(ctx.session, own, trained.evaluations["sys1"])
        if trained.status == "succeeded" and "base" in trained.evaluations:
            records["base"] = _records(ctx.session, own, trained.evaluations["base"])
        if scored_remotely:
            pass
        elif trained.status == "succeeded" and trained.adapter_ref and _serves(providers.sys1, trained.adapter_ref):
            progress.stage = "testing"
            records["sys1"] = await evaluate_lane(
                ctx.session, providers, own, "sys1", test_set_version, policy_and_version=(policy, policy_version)
            )
        elif trained.status == "preview":
            sys1_note = ReportRow(key="sys1", label=LABELS["sys1"], status="preview", message=PREVIEW_MESSAGE)
        elif trained.status == "succeeded":
            # The server's sys1 endpoint may be serving some other model; only a match to this run's adapter is scored.
            sys1_note = ReportRow(key="sys1", label=LABELS["sys1"], status="preview", message=NOT_CONNECTED_MESSAGE)
        else:
            sys1_note = ReportRow(key="sys1", label=LABELS["sys1"], status="unavailable", message=trained.message)

        test_per_bucket = _test_per_bucket(ctx.session, own, policy)
        rows, verdict, details = assemble(records, sys1_note, test_per_bucket, preview=trained.status == "preview")
        details.trainer = type(providers.trainer).__name__
        details.adapter_ref = trained.adapter_ref
        card = ReportCard(
            org_id=org_id,
            project_id=project_id,
            job_id=job.id,
            test_set_version=test_set_version,
            policy_version=policy_version,
            dataset_version=dataset_version,
            rows_json=[r.model_dump() for r in rows],
            verdict_json=verdict.model_dump(),
            details_json=details.model_dump(),
            is_preview=trained.status == "preview",
        )
        ctx.session.add(card)
        ctx.session.commit()
        # Only a trainer that produced a model ends the job as "succeeded".
        if trained.status == "preview":
            ctx.final_status, ctx.message = "preview", PREVIEW_MESSAGE
        elif trained.status == "unavailable":
            ctx.final_status, ctx.message = "unavailable", trained.message
        elif sys1_note is not None:
            ctx.message = NOT_CONNECTED_MESSAGE
        return {
            **summary,
            "report_card_id": card.id,
            "trainer_status": trained.status,
            **({"training": progress.detail} if progress.detail else {}),
        }

    job_service.start_job(job_service.session_factory_for(session), job.id, work)
    return job.id


class _Progress:
    """Turns the trainer's stage and the share of Jev answers collected into one job progress value."""

    def __init__(self, ctx: JobContext):
        self._ctx = ctx
        self.stage = "preparing"
        self._trainer = 0.0
        self._scoring = 0.0
        self.detail: dict | None = None

    def trainer(self, stage: str | None, done: bool = False, detail: dict | None = None) -> None:
        self.stage = stage if stage in STAGE_PROGRESS else self.stage
        self._trainer = 1.0 if done else STAGE_PROGRESS[self.stage]
        step, total = (detail or {}).get("step"), (detail or {}).get("total_steps")
        if self.stage == "learning" and step is not None and total:
            # Move through the learning stage as steps finish, instead of sitting at one value.
            self._trainer = 0.1 + 0.55 * min(1.0, step / total)
        if detail:
            self.detail = detail
        if done:
            self.stage = "testing"
        self._push()

    def scored(self, share: float) -> None:
        self._scoring = share
        self._push()

    def _push(self) -> None:
        self._ctx.progress(
            min(0.99, TRAINER_SHARE * self._trainer + (1 - TRAINER_SHARE) * self._scoring),
            self.stage,
            {"training": self.detail} if self.detail else None,
        )


async def _run_trainer(providers: Providers, dataset_ref: str, config: dict, progress: _Progress) -> TrainingJob:
    # Trainers may block on the network, so they run off the event loop.
    job = await asyncio.to_thread(providers.trainer.start, dataset_ref, config)
    while job.status in ("queued", "running"):
        progress.trainer(job.metrics.get("stage"), detail=job.metrics.get("detail"))
        await asyncio.sleep(POLL_INTERVAL_S)
        job = await asyncio.to_thread(providers.trainer.status, job.id)
    progress.trainer(None, done=True)
    return job


def _records(session: Session, project: Project, answers: list[EvalAnswer]) -> list[PredRecord]:
    """Scores a trainer's answers against our own gold labels; a test example it skipped counts as wrong."""
    by_id = {a.id: a for a in answers}
    records = []
    for example in load_test_examples(session, project):
        answer = by_id.get(example.id)
        if answer is None or answer.pred is None:
            records.append(PredRecord(id=example.id, gold=example.label, error="No answer."))
        else:
            records.append(
                PredRecord(
                    id=example.id,
                    gold=example.label,
                    pred=answer.pred,
                    p_gold=answer.p_gold,
                    latency_ms=answer.latency_ms,
                    correct=answer.pred.lower() == example.label.lower(),
                )
            )
    return records


def _test_per_bucket(session: Session, project: Project, policy: Policy) -> dict[str, int]:
    counts = dict.fromkeys((o.key for o in policy.options), 0)
    for example in load_test_examples(session, project):
        counts[example.label] = counts.get(example.label, 0) + 1
    return counts


# ---- reading the latest card ------------------------------------------------------------------------------------


def _fixture_report(session: Session, project: Project) -> Report | None:
    """The recorded results that ship with the flagship template, shown until a run of its own produces a card."""
    if project.template_id is None:
        return None
    try:
        template = get_template(project.template_id)
    except KeyError:
        return None
    if template.flagship is None:
        return None
    runs = EvalFilesSource(template.flagship.eval_dir, template.flagship.eval_models).runs()
    if not runs:
        return None
    # The recorded files call the guidelines run "jev_policy".
    keys: dict[str, RowKey] = {"sys1": "sys1", "jev_policy": "jev", "base": "base"}
    records: dict[RowKey, list[PredRecord]] = {
        keys[run.model_key]: [
            PredRecord(id=r.id, gold=r.gold, pred=r.pred, p_gold=r.p_gold, correct=r.correct) for r in run.records
        ]
        for run in runs
        if run.model_key in keys
    }
    policy, _ = project_service.latest_policy(session, project)
    buckets = dict.fromkeys((o.key for o in policy.options), 0)
    for record in next(iter(records.values())):
        buckets[record.gold] = buckets.get(record.gold, 0) + 1
    # Recorded sample numbers come from a smaller set than a real run, so the "too few" rule only applies to real cards.
    rows, verdict, details = assemble(records, None, buckets, skip_few_check=True)
    return Report(
        available=True,
        rows=rows,
        verdict=verdict,
        details=details,
        is_fixture=any(run.is_fixture for run in runs),
    )


def report(session: Session, project: Project) -> Report:
    """The latest report card. Callers must already have checked the project belongs to their org."""
    card = session.scalars(
        select(ReportCard).where(ReportCard.project_id == project.id).order_by(ReportCard.created_at.desc())
    ).first()
    if card is None:
        return _fixture_report(session, project) or Report(available=False)
    details = ReportDetails(**card.details_json)
    return Report(
        available=True,
        rows=[ReportRow(**r) for r in card.rows_json],
        verdict=Verdict(**card.verdict_json),
        details=details,
        is_preview=card.is_preview,
        test_set_version=card.test_set_version,
        too_few_test=too_few(details.test_per_bucket),
        job_id=card.job_id,
    )


async def _confirmed_training(ctx: AgentContext, action: PendingAction) -> dict:
    return {"job_id": start_training(ctx.session, ctx.providers, ctx.settings, ctx.principal, ctx.project)}


register_action_handler("training", _confirmed_training)
