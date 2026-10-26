import asyncio
import json
from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel
from sqlalchemy.orm import Session

from system1.adapters.eval_files import EvalFilesSource
from system1.adapters.jsonl_dataset import JsonlDatasetSource
from system1.config import get_settings
from system1.contracts.datasets import DatasetRow
from system1.contracts.decisions import DecisionProvider, DecisionRequest, DecisionResponse, ProviderError
from system1.decisions.models import Decision
from system1.domain.policy import Policy
from system1.domain.questions import build_questions
from system1.errors import InputTooLong, NotFound
from system1.projects.models import Project
from system1.projects.service import latest_policy
from system1.providers import Providers
from system1.registry.service import live_adapter
from system1.templates.catalog import Template, get_template

Lane = Literal["jev", "jev_labels", "sys1"]
State = str | dict | list

NO_LIVE_MODEL = "This project has no live model yet. Train one, or pick one to make live."


class LaneResult(BaseModel):
    lane: Lane
    label: str | None = None
    probabilities: dict[str, float] = {}
    model: str | None = None
    latency_ms: float | None = None
    decision_id: str | None = None
    error: str | None = None
    retryable: bool = False


class TryResult(BaseModel):
    results: list[LaneResult]
    gold: str | None = None
    rule_id: str | None = None
    # Predictions saved from an offline evaluation run, not live calls. The UI labels them "recorded".
    recorded: dict[str, str] = {}
    # True while any recorded prediction comes from sample (fixture) numbers; the UI shows a banner then.
    recorded_is_fixture: bool = False


def _flagship(project: Project) -> Template | None:
    if project.template_id is None:
        return None
    try:
        template = get_template(project.template_id)
    except KeyError:
        return None
    return template if template.flagship else None


def questions_for(project: Project, policy: Policy, lane: Lane) -> dict:
    variant = "policy" if lane == "jev" else "labels"
    template = _flagship(project)
    if template and template.flagship:
        return json.loads(template.flagship.jev_questions_path.read_text())[variant]
    return build_questions(policy, variant)


def flagship_rows(project: Project) -> list[DatasetRow]:
    template = _flagship(project)
    if template is None or template.flagship is None:
        return []
    return JsonlDatasetSource(template.flagship.samples_path).rows("test")


def check_length(state: State) -> None:
    length = len(state) if isinstance(state, str) else len(json.dumps(state))
    limit = get_settings().max_input_chars
    if length > limit:
        raise InputTooLong(length, limit)


def _provider(providers: Providers, lane: Lane) -> DecisionProvider | None:
    return providers.sys1 if lane == "sys1" else providers.jev


def _sys1_model(session: Session, provider: DecisionProvider, project: Project) -> tuple[str, str | None]:
    """The model name to ask sys1 for, and the trained model it is. A provider that runs whichever adapter it is
    handed answers with the project's live model; raises LookupError when there isn't one."""
    if not getattr(provider, "serves_adapters", False):
        return get_settings().sys1_model, None
    adapter = live_adapter(session, project)
    if adapter is None:
        raise LookupError(NO_LIVE_MODEL)
    return adapter, project.live_model_id


def sys1_ready(session: Session, providers: Providers, project: Project) -> bool:
    if providers.sys1 is None:
        return False
    return not getattr(providers.sys1, "serves_adapters", False) or live_adapter(session, project) is not None


async def run_lane(
    session: Session,
    providers: Providers,
    project: Project,
    state: State,
    lane: Lane,
    source: Literal["playground", "api", "agent", "eval"],
    *,
    policy_and_version: tuple[Policy, int] | None = None,
    dataset_row_id: str | None = None,
) -> LaneResult:
    check_length(state)
    provider = _provider(providers, lane)
    if provider is None:
        return LaneResult(lane=lane, error="sys1 isn't connected yet.")
    model = get_settings().jev_model
    sys1_model_id: str | None = None
    if lane == "sys1":
        try:
            model, sys1_model_id = _sys1_model(session, provider, project)
        except LookupError:
            return LaneResult(lane=lane, error=NO_LIVE_MODEL)
    policy, version = policy_and_version or latest_policy(session, project)
    questions = questions_for(project, policy, lane)
    try:
        response = await provider.decide(DecisionRequest(model=model, state=state, questions=questions))
    except ProviderError as exc:
        return LaneResult(lane=lane, error=exc.user_message, retryable=exc.retryable)

    answer = response.answers.get(next(iter(questions)))
    label = answer.choice if answer else None
    probabilities = answer.probabilities if answer else {}
    decision = Decision(
        org_id=project.org_id,
        project_id=project.id,
        source=source,
        lane=lane,
        model_reported=response.model,
        state_json=state,
        answers_json={k: v.model_dump() for k, v in response.answers.items()},
        top_label=label,
        top_prob=probabilities.get(label) if label else None,
        latency_ms=response.latency_ms,
        policy_version=version,
        not_for_training=lane.startswith("jev"),
        dataset_row_id=dataset_row_id,
        sys1_model_id=sys1_model_id,
    )
    session.add(decision)
    session.commit()
    return LaneResult(
        lane=lane,
        label=label,
        probabilities=probabilities,
        model=response.model,
        latency_ms=response.latency_ms,
        decision_id=decision.id,
    )


async def try_input(
    session: Session,
    providers: Providers,
    project: Project,
    text_or_state: State | None = None,
    sample_id: str | None = None,
    only: tuple[Lane, ...] | None = None,
) -> TryResult:
    """`only` limits the lanes that run (the assistant's quick check leaves your own model out)."""
    row: DatasetRow | None = None
    if sample_id is not None:
        row = next((r for r in flagship_rows(project) if r.id == sample_id), None)
        if row is None:
            raise NotFound("Sample not found.")
        state: State = row.state
    elif text_or_state is not None:
        state = text_or_state
    else:
        raise NotFound("Send some text or pick a sample.")
    check_length(state)

    policy_and_version = latest_policy(session, project)
    lanes: list[Lane] = (
        list(only) if only else ["jev_labels", "jev"] + (["sys1"] if sys1_ready(session, providers, project) else [])
    )
    # Lanes share one session but never await between touching it, so gather is safe on a single thread.
    results = await asyncio.gather(
        *(
            run_lane(
                session,
                providers,
                project,
                state,
                lane,
                "playground",
                policy_and_version=policy_and_version,
                dataset_row_id=sample_id,
            )
            for lane in lanes
        )
    )
    if row is None:
        return TryResult(results=list(results))

    template = _flagship(project)
    recorded: dict[str, str] = {}
    recorded_is_fixture = False
    if template and template.flagship:
        flagship = template.flagship
        for run in EvalFilesSource(flagship.eval_dir, flagship.eval_models).runs():
            record = next((r for r in run.records if r.id == row.id), None)
            if record:
                recorded[run.model_key] = record.pred
                recorded_is_fixture = recorded_is_fixture or run.is_fixture
    key = next(iter(row.gold), None)
    return TryResult(
        results=list(results),
        gold=row.gold.get(key) if key else None,
        rule_id=row.metadata.get("rule_id"),
        recorded=recorded,
        recorded_is_fixture=recorded_is_fixture,
    )


BATCH_CHUNK = 100  # rows per call to the model, so a batch shows progress as it goes
BATCH_CONCURRENCY = 4  # for providers without a batch call, one decision per request


async def run_batch(
    session: Session,
    providers: Providers,
    project: Project,
    states: list[str],
    batch_id: str,
    on_progress: Callable[[float], None] | None = None,
) -> tuple[list[Decision], int]:
    """Your live model on every state. Returns the saved decisions and how many states got no answer."""
    provider = providers.sys1
    if provider is None:
        raise ProviderError(NO_LIVE_MODEL)
    try:
        model, sys1_model_id = _sys1_model(session, provider, project)
    except LookupError as exc:
        raise ProviderError(NO_LIVE_MODEL) from exc
    policy, version = latest_policy(session, project)
    questions = questions_for(project, policy, "sys1")
    gate = asyncio.Semaphore(BATCH_CONCURRENCY)

    async def one(state: str) -> DecisionResponse | None:
        async with gate:
            try:
                return await provider.decide(DecisionRequest(model=model, state=state, questions=questions))
            except ProviderError:
                return None

    decisions: list[Decision] = []
    failed = 0
    for start in range(0, len(states), BATCH_CHUNK):
        chunk = states[start : start + BATCH_CHUNK]
        decide_many = getattr(provider, "decide_many", None)
        if decide_many is not None:
            responses: list[DecisionResponse | None] = list(await decide_many(model, chunk, questions))
        else:
            responses = list(await asyncio.gather(*(one(s) for s in chunk)))
        for state, response in zip(chunk, responses, strict=True):
            answer = response.answers.get(next(iter(questions))) if response else None
            if response is None or answer is None:
                failed += 1
                continue
            decision = Decision(
                org_id=project.org_id,
                project_id=project.id,
                source="batch",
                lane="sys1",
                model_reported=response.model,
                state_json=state,
                answers_json={k: v.model_dump() for k, v in response.answers.items()},
                top_label=answer.choice,
                top_prob=answer.probabilities.get(answer.choice),
                latency_ms=response.latency_ms,
                policy_version=version,
                sys1_model_id=sys1_model_id,
                batch_id=batch_id,
            )
            session.add(decision)
            decisions.append(decision)
        session.commit()
        if on_progress:
            on_progress(min(1.0, (start + len(chunk)) / len(states)))
    return decisions, failed
