from sqlalchemy import select
from sqlalchemy.orm import Session

from system1.auth.principal import Principal
from system1.errors import NotFound
from system1.projects.models import Project
from system1.registry.schemas import ModelOut
from system1.report.models import ReportCard


def is_model(card: ReportCard) -> bool:
    """A run counts as a model only if the trainer produced an adapter; preview runs never do."""
    return not card.is_preview and bool((card.details_json or {}).get("adapter_ref"))


def _row(card: ReportCard, key: str) -> dict:
    return next((r for r in card.rows_json if r.get("key") == key), {})


def _out(card: ReportCard, project: Project) -> ModelOut:
    mine, jev = _row(card, "sys1"), _row(card, "jev")
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
    return [_out(card, project) for card, project in session.execute(stmt).all() if is_model(card)]


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


def adopt_if_first(session: Session, project: Project, card: ReportCard) -> None:
    """A project's first trained model goes live by itself; later ones wait for someone to pick them."""
    if project.live_model_id is None and is_model(card):
        project.live_model_id = card.id
        session.commit()


def live_adapter(session: Session, project: Project) -> str | None:
    if project.live_model_id is None:
        return None
    card = session.get(ReportCard, project.live_model_id)
    return card.details_json.get("adapter_ref") if card and is_model(card) else None
