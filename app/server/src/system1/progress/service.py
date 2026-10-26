from sqlalchemy.orm import Session

from system1.datasets import service as dataset_service
from system1.datasets.constants import MIN_PER_BUCKET, REVIEW_CARDS
from system1.domain.policy import validate_policy
from system1.gateway import keys
from system1.progress.schemas import ProjectProgress, StageId, StageState
from system1.projects import service as project_service
from system1.projects.models import Project
from system1.report import service as report_service
from system1.report.schemas import Report
from system1.templates.catalog import get_template

JOURNEY: tuple[StageId, ...] = ("define", "data", "review", "train", "use", "improve")


def _is_flagship(project: Project) -> bool:
    if project.template_id is None:
        return False
    try:
        return get_template(project.template_id).flagship is not None
    except KeyError:
        return False


def _accuracy(report: Report, key: str) -> float | None:
    return next((r.accuracy for r in report.rows if r.key == key), None)


def _data_note(total: int, short: int) -> str:
    if total == 0:
        return "No examples yet"
    return "1 bucket needs more examples" if short == 1 else f"{short} buckets need more examples"


def progress(session: Session, project: Project) -> ProjectProgress:
    """Where a project stands on each stage. Callers must already have checked the project belongs to their org."""
    policy, _ = project_service.latest_policy(session, project)
    health = dataset_service.health(session, project)
    report = report_service.report(session, project)

    total = sum(counts["total"] for counts in health.per_bucket.values())
    short = len(health.below_minimum)
    accuracy = _accuracy(report, "sys1")
    flagship = _is_flagship(project)
    states: dict[StageId, StageState] = {}

    if len(policy.options) < 2:
        define_done = False
        states["define"] = StageState(id="define", status="ready", note="Add at least two buckets")
    elif validate_policy(policy):
        define_done = False
        states["define"] = StageState(id="define", status="ready", note="Fix the problems in your buckets")
    else:
        define_done = True
        states["define"] = StageState(id="define", status="done", note=f"{len(policy.options)} buckets")

    if not define_done:
        states["data"] = StageState(id="data", status="blocked", note="Define your buckets first")
    elif flagship:
        # The flagship's labels come from exact rules and its results are recorded, so it has no examples to add.
        states["data"] = StageState(id="data", status="done", note="Built with exact rules")
    elif total > 0 and short == 0:
        states["data"] = StageState(id="data", status="done", note=f"{total} examples")
    else:
        states["data"] = StageState(id="data", status="ready", note=_data_note(total, short))

    if flagship:
        states["review"] = StageState(id="review", status="done", note="Labelled by exact rules")
    elif total == 0:
        states["review"] = StageState(id="review", status="blocked", note="Add examples first")
    else:
        queued = len(dataset_service.review_queue(session, project))
        if queued == 0:
            states["review"] = StageState(id="review", status="done", note="Nothing left to check")
        else:
            states["review"] = StageState(
                id="review",
                status="ready",
                note=f"{queued}+ to check" if queued == REVIEW_CARDS else f"{queued} to check",
            )

    if report.available:
        # A preview run has no model behind it, so it must not read as a trained one.
        note = f"Your model: {round(accuracy * 100)}%" if accuracy is not None else "Preview run, no model yet"
        states["train"] = StageState(id="train", status="done", note=note)
    elif total == 0 or short > 0:
        states["train"] = StageState(id="train", status="blocked", note=f"Needs {MIN_PER_BUCKET} examples per bucket")
    else:
        states["train"] = StageState(id="train", status="ready", note="Ready to train")

    if not define_done:
        states["use"] = StageState(id="use", status="blocked", note="Define your buckets first")
    elif keys.list_keys(session, project):
        states["use"] = StageState(id="use", status="done", note="Connected")
    else:
        states["use"] = StageState(id="use", status="ready", note="Try it, then get a key")

    if project.live_model_id is None:
        states["improve"] = StageState(id="improve", status="blocked", note="Needs a live model")
    else:
        states["improve"] = StageState(id="improve", status="ready", note="Check what your model wasn't sure about")

    stages = [states[sid] for sid in JOURNEY]
    return ProjectProgress(
        stages=stages,
        next=next((s.id for s in stages if s.status == "ready"), None),
        examples=total,
        accuracy=accuracy,
        jev_accuracy=_accuracy(report, "jev"),
    )
