from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from system1.auth.principal import Principal
from system1.decisions.models import Decision, Feedback
from system1.errors import ApiError, NotFound
from system1.projects.models import Project
from system1.registry.schemas import BucketChange, Comparison, ModelOut
from system1.report.models import ReportCard

# Bucket changes smaller than this are noise on a typical test set, so they aren't listed.
BUCKET_CHANGE_MIN = 0.05
BUCKETS_SHOWN = 5
# Each model is a GPU training run plus an adapter kept on the Modal volume, so an org keeps only this many.
MAX_MODELS_PER_ORG = 2


class ModelLimitReached(ApiError):
    status_code = 409
    code = "model_limit_reached"
    message = (
        f"You can keep {MAX_MODELS_PER_ORG} models, and they're all live. Turn one off or delete it to train another."
    )


def is_model(card: ReportCard) -> bool:
    """A run counts as a model only if the trainer produced an adapter; preview runs never do."""
    return not card.is_preview and bool((card.details_json or {}).get("adapter_ref"))


def _row(card: ReportCard, key: str) -> dict:
    return next((r for r in card.rows_json if r.get("key") == key), {})


def _checks(session: Session, model_ids: list[str]) -> dict[str, tuple[int, int]]:
    """Per model: (answers your team checked, how many it had right). A confirm means right; a correction to a
    different bucket means wrong."""
    if not model_ids:
        return {}
    right = func.sum(case((Feedback.correct_label == Decision.top_label, 1), else_=0))
    rows = session.execute(
        select(Decision.sys1_model_id, func.count(Feedback.id), right)
        .join(Feedback, Feedback.decision_id == Decision.id)
        .where(Decision.sys1_model_id.in_(model_ids), Decision.source != "eval")
        .group_by(Decision.sys1_model_id)
    )
    return {model_id: (checked, int(ok or 0)) for model_id, checked, ok in rows}


def _out(card: ReportCard, project: Project, checks: dict[str, tuple[int, int]] | None = None) -> ModelOut:
    mine, jev = _row(card, "sys1"), _row(card, "jev")
    checked, checked_right = (checks or {}).get(card.id, (0, 0))
    return ModelOut(
        id=card.id,
        project_id=project.id,
        project_name=project.name,
        created_at=card.created_at,
        live=project.live_model_id == card.id,
        accuracy=mine.get("accuracy"),
        jev_accuracy=jev.get("accuracy"),
        test_examples=mine.get("n"),
        median_latency_ms=mine.get("median_latency_ms"),
        test_set_version=card.test_set_version,
        corrections_used=(card.details_json or {}).get("corrections_used"),
        size=(card.details_json or {}).get("size"),
        checked=checked,
        checked_right=checked_right,
    )


def list_models(session: Session, principal: Principal, project_id: str | None = None) -> list[ModelOut]:
    """The org's trained models, newest first."""
    stmt = (
        select(ReportCard, Project)
        .join(Project, Project.id == ReportCard.project_id)
        .where(Project.org_id == principal.org_id, ReportCard.is_preview.is_(False))
        .order_by(ReportCard.created_at.desc())
    )
    if project_id is not None:
        stmt = stmt.where(Project.id == project_id)
    pairs = [(card, project) for card, project in session.execute(stmt).all() if is_model(card)]
    checks = _checks(session, [card.id for card, _ in pairs])
    return [_out(card, project, checks) for card, project in pairs]


def get_model(session: Session, principal: Principal, model_id: str) -> tuple[ReportCard, Project]:
    card = session.get(ReportCard, model_id)
    project = session.get(Project, card.project_id) if card else None
    if card is None or project is None or project.org_id != principal.org_id or not is_model(card):
        raise NotFound("Model not found.")
    return card, project


def make_live(session: Session, principal: Principal, model_id: str) -> Project:
    card, project = get_model(session, principal, model_id)
    project.live_model_id = card.id
    session.commit()
    return project


def turn_off(session: Session, principal: Principal, model_id: str) -> Project:
    """Clears the project's live model if it is this one; turning off a model that isn't live changes nothing."""
    card, project = get_model(session, principal, model_id)
    if project.live_model_id == card.id:
        project.live_model_id = None
        session.commit()
    return project


def delete_model(session: Session, principal: Principal, model_id: str) -> Project:
    """Removes the run and its report card. A live model stops serving first. Decisions it already made keep
    their record, and the adapter's files are left where the trainer stored them."""
    card, project = get_model(session, principal, model_id)
    if project.live_model_id == card.id:
        project.live_model_id = None
    session.delete(card)
    session.commit()
    return project


def adopt_if_first(session: Session, project: Project, card: ReportCard) -> None:
    """A project's first trained model goes live by itself; later ones wait for someone to pick them."""
    if project.live_model_id is None and is_model(card):
        project.live_model_id = card.id
        session.commit()


def _org_models(session: Session, org_id: str) -> list[tuple[ReportCard, Project]]:
    """The org's models, oldest first."""
    stmt = (
        select(ReportCard, Project)
        .join(Project, Project.id == ReportCard.project_id)
        .where(Project.org_id == org_id, ReportCard.is_preview.is_(False))
        .order_by(ReportCard.created_at)
    )
    return [(card, project) for card, project in session.execute(stmt).all() if is_model(card)]


def check_room(session: Session, org_id: str) -> None:
    """A new run will replace the oldest model that isn't live, so it can start unless every kept model is live."""
    models = _org_models(session, org_id)
    if len(models) >= MAX_MODELS_PER_ORG and all(project.live_model_id == card.id for card, project in models):
        raise ModelLimitReached()


def retire_extra(session: Session, org_id: str, keep_id: str) -> list[str]:
    """Drops the oldest models that aren't live until the org is back at the limit, and returns their adapter refs.

    The card stays, so past decisions and the report history still resolve; it just stops counting as a model."""
    models = _org_models(session, org_id)
    retired: list[str] = []
    for card, project in models:
        if len(models) - len(retired) <= MAX_MODELS_PER_ORG:
            break
        if card.id == keep_id or project.live_model_id == card.id:
            continue
        retired.append(card.details_json["adapter_ref"])
        # Reassigned, not mutated, so SQLAlchemy sees the JSON column change.
        card.details_json = {**card.details_json, "adapter_ref": None}
    session.commit()
    return retired


def live_adapter(session: Session, project: Project) -> str | None:
    if project.live_model_id is None:
        return None
    card = session.get(ReportCard, project.live_model_id)
    return card.details_json.get("adapter_ref") if card and is_model(card) else None


def _per_bucket(card: ReportCard) -> dict[str, float]:
    return ((card.details_json or {}).get("per_bucket") or {}).get("sys1") or {}


def compare(session: Session, principal: Principal, model_id: str) -> Comparison:
    """A model next to the project's live one, on the same frozen test set when both were scored on it."""
    card, project = get_model(session, principal, model_id)
    live_card = session.get(ReportCard, project.live_model_id) if project.live_model_id else None
    ids = [card.id] + ([live_card.id] if live_card else [])
    checks = _checks(session, ids)
    candidate = _out(card, project, checks)
    live = _out(live_card, project, checks) if live_card else None

    if live is None or live.id == candidate.id:
        sentence = "This is the live model." if live else "No model is live yet, so this one can go live."
        return Comparison(
            candidate=candidate,
            live=live,
            same_test_set=True,
            diff=None,
            improved=[],
            worsened=[],
            recommend=live is None,
            sentence=sentence,
        )
    same = card.test_set_version == live_card.test_set_version
    if not same or candidate.accuracy is None or live.accuracy is None:
        return Comparison(
            candidate=candidate,
            live=live,
            same_test_set=same,
            diff=None,
            improved=[],
            worsened=[],
            recommend=False,
            sentence="These two were tested on different test examples, so their scores can't be compared."
            if not same
            else "One of these wasn't scored, so there's nothing to compare.",
        )

    diff = candidate.accuracy - live.accuracy
    before, after = _per_bucket(live_card), _per_bucket(card)
    changes = [BucketChange(key=k, before=before[k], after=after[k]) for k in after if k in before]
    improved = sorted((c for c in changes if c.after - c.before >= BUCKET_CHANGE_MIN), key=lambda c: c.before - c.after)
    worsened = sorted((c for c in changes if c.before - c.after >= BUCKET_CHANGE_MIN), key=lambda c: c.after - c.before)
    points = round(diff * 100)
    if points > 0:
        sentence = f"It gets {points} more test examples right out of every 100 than the live model. Make it live?"
    elif points < 0:
        sentence = f"It gets {-points} fewer right out of every 100 than the live model, so keep the live one."
    else:
        sentence = "It scores the same as the live model on the test examples, so there's no reason to switch."
    return Comparison(
        candidate=candidate,
        live=live,
        same_test_set=True,
        diff=diff,
        improved=improved[:BUCKETS_SHOWN],
        worsened=worsened[:BUCKETS_SHOWN],
        recommend=points > 0,
        sentence=sentence,
    )
