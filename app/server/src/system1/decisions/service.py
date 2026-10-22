from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from system1.auth.principal import Principal
from system1.decisions.models import Decision, Feedback
from system1.errors import ApiError, NotFound
from system1.gateway.service import flagship_rows
from system1.projects.models import Project, now
from system1.projects.service import latest_policy

Kind = Literal["confirm", "correction", "api_correction"]


class BadLabel(ApiError):
    status_code = 422
    code = "invalid_label"
    message = "That isn't one of this project's options."


def question_key(session: Session, project: Project) -> str:
    return latest_policy(session, project)[0].question_key


def _is_test_item(decision: Decision, project: Project) -> bool:
    # Flagship samples are all test-split tickets; the model never trains on those.
    return decision.dataset_row_id is not None and any(r.id == decision.dataset_row_id for r in flagship_rows(project))


def record_feedback(
    session: Session, principal: Principal | None, decision: Decision, kind: Kind, correct_label: str | None
) -> Feedback:
    """The one place that decides whether feedback may be trained on.

    A confirmed Jev answer is never eligible (Jev output must not become a label); a person's
    correction is, because the person supplies the label.
    """
    project = session.get(Project, decision.project_id)
    if project is None:
        raise NotFound("Project not found.")
    policy, _ = latest_policy(session, project)
    label = decision.top_label if kind == "confirm" else correct_label
    options = {o.key for o in policy.options}
    if kind == "confirm" and label not in options:
        raise BadLabel("That answer isn't one of the current options, so it can't be confirmed. Pick the right one.")
    if label is None or label not in options:
        raise BadLabel()
    is_test = _is_test_item(decision, project)
    # The latest verdict wins: one row per decision, so repeats never inflate the training pool.
    # (Enforced here rather than by a UNIQUE constraint, which SQLite can't add to an existing table.)
    row = session.scalars(select(Feedback).where(Feedback.decision_id == decision.id)).first()
    if row is None:
        row = Feedback(org_id=decision.org_id, project_id=decision.project_id, decision_id=decision.id)
        session.add(row)
    row.correct_json = {policy.question_key: label}
    row.kind = kind
    row.user_id = principal.user_id if principal else None
    row.correct_label = label
    row.is_test_item = is_test
    row.training_eligible = not is_test and (decision.lane == "sys1" or kind in ("correction", "api_correction"))
    row.created_at = now()
    # A verdict settles whatever question made this decision worth a look.
    decision.needs_review = False
    session.commit()
    return row


def inbox(session: Session, project: Project) -> list[Decision]:
    """Decisions worth a human look. Jev's answers never decide what shows up or what the label is."""
    judged = select(Feedback.decision_id).where(Feedback.project_id == project.id)
    stmt = (
        select(Decision)
        .where(Decision.project_id == project.id, Decision.needs_review.is_(True), Decision.id.not_in(judged))
        .order_by(Decision.created_at.desc())
        .limit(100)
    )
    return list(session.scalars(stmt))


def training_pool_count(session: Session, project: Project) -> int:
    stmt = select(func.count(func.distinct(Feedback.decision_id))).where(
        Feedback.project_id == project.id, Feedback.training_eligible.is_(True)
    )
    return session.scalar(stmt) or 0
