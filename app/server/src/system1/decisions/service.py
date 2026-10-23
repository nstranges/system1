from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from system1.auth.principal import Principal
from system1.decisions.models import Decision, Feedback
from system1.errors import ApiError, NotFound
from system1.gateway.service import flagship_rows
from system1.jobs.models import Job
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


# Margins are computed in Python from stored probabilities, so only the newest answers are considered.
INBOX_SCAN = 1000
INBOX_LIMIT = 100
INBOX_FLAGGED_RESERVE = 20


def margin(decision: Decision) -> float:
    """Top probability minus the runner-up, from the stored probabilities. 1.0 when there are fewer than two."""
    for answer in decision.answers_json.values():
        probs = sorted((answer.get("probabilities") or {}).values(), reverse=True)
        if len(probs) >= 2:
            return probs[0] - probs[1]
        break
    return 1.0


def inbox(session: Session, project: Project) -> list[tuple[Decision, float | None]]:
    """Decisions worth a human look, each with its "how sure" (None for flagged ones).

    First the model's own answers nobody has judged, least sure first. Then anything flagged for review, newest
    first. Jev's answers are never ranked or chosen by what Jev said: a flagged Jev answer is there because the
    model was unsure, and sits in the recency group.
    """
    judged = select(Feedback.decision_id).where(Feedback.project_id == project.id)
    base = select(Decision).where(Decision.project_id == project.id, Decision.id.not_in(judged))
    sys1 = session.scalars(
        base.where(Decision.lane == "sys1", Decision.source != "eval")
        .order_by(Decision.created_at.desc())
        .limit(INBOX_SCAN)
    )
    ranked = sorted(((d, margin(d)) for d in sys1), key=lambda pair: pair[1])
    flagged = session.scalars(
        base.where(Decision.needs_review.is_(True)).order_by(Decision.created_at.desc()).limit(INBOX_LIMIT)
    )
    # Room is kept for flagged items so a long run of unsure answers can't push them out of the list.
    kept = ranked[: INBOX_LIMIT - INBOX_FLAGGED_RESERVE]
    kept_ids = {d.id for d, _ in kept}
    out: list[tuple[Decision, float | None]] = [*kept]
    out += [(d, None) for d in flagged if d.id not in kept_ids][: INBOX_LIMIT - len(out)]
    if len(out) < INBOX_LIMIT:
        shown = {d.id for d, _ in out}
        out += [pair for pair in ranked[len(kept) :] if pair[0].id not in shown][: INBOX_LIMIT - len(out)]
    return out


def training_pool_count(session: Session, project: Project) -> int:
    """Eligible corrections made since the project's latest training job (of any status); all of them if it never trained."""
    stmt = select(func.count(func.distinct(Feedback.decision_id))).where(
        Feedback.project_id == project.id, Feedback.training_eligible.is_(True)
    )
    last_training = session.scalar(
        select(func.max(Job.created_at)).where(Job.project_id == project.id, Job.kind == "training")
    )
    if last_training is not None:
        stmt = stmt.where(Feedback.created_at > last_training)
    return session.scalar(stmt) or 0
