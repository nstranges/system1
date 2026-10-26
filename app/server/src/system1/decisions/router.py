from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from system1.auth.deps import get_principal
from system1.auth.principal import Principal
from system1.db import get_session
from system1.decisions import service
from system1.decisions.models import Decision
from system1.errors import NotFound
from system1.projects.service import get_project
from system1.registry.service import list_models

router = APIRouter(dependencies=[Depends(get_principal)])

PrincipalDep = Annotated[Principal, Depends(get_principal)]
SessionDep = Annotated[Session, Depends(get_session)]


class FeedbackIn(BaseModel):
    kind: Literal["confirm", "correction"]
    correct_label: str | None = None


class FeedbackOut(BaseModel):
    status: str = "recorded"


class Guess(BaseModel):
    key: str
    p: float


class InboxItem(BaseModel):
    decision_id: str
    state: str | dict | list
    answer: str | None
    lane: str
    created_at: datetime
    # The gap between the top two answers; lowest is least sure. None for items flagged for review.
    how_sure: float | None = None
    # The model's top answers, most likely first, so the right bucket is usually one click away.
    guesses: list[Guess] = []


class InboxOut(BaseModel):
    items: list[InboxItem]


class ImproveSummary(BaseModel):
    waiting: int
    # Corrections since the last training that the next one will learn from.
    ready: int
    # Answers from the live model that your team checked, and how many it had right.
    live_checked: int
    live_right: int


class PoolOut(BaseModel):
    count: int


@router.post("/decisions/{decision_id}/feedback")
def post_feedback(decision_id: str, body: FeedbackIn, principal: PrincipalDep, session: SessionDep) -> FeedbackOut:
    decision = session.get(Decision, decision_id)
    if decision is None or decision.org_id != principal.org_id:
        raise NotFound("Decision not found.")
    service.record_feedback(session, principal, decision, body.kind, body.correct_label)
    return FeedbackOut()


@router.get("/projects/{project_id}/inbox")
def get_inbox(project_id: str, principal: PrincipalDep, session: SessionDep) -> InboxOut:
    project = get_project(session, principal, project_id)
    return InboxOut(
        items=[
            InboxItem(
                decision_id=d.id,
                state=d.state_json,
                answer=d.top_label,
                lane=d.lane,
                created_at=d.created_at,
                how_sure=how_sure,
                guesses=[Guess(key=k, p=p) for k, p in service.guesses(d)],
            )
            for d, how_sure in service.inbox(session, project)
        ]
    )


@router.get("/projects/{project_id}/training-pool")
def get_training_pool(project_id: str, principal: PrincipalDep, session: SessionDep) -> PoolOut:
    project = get_project(session, principal, project_id)
    return PoolOut(count=service.training_pool_count(session, project))


@router.get("/projects/{project_id}/improve")
def get_improve_summary(project_id: str, principal: PrincipalDep, session: SessionDep) -> ImproveSummary:
    project = get_project(session, principal, project_id)
    live = next((m for m in list_models(session, principal, project.id) if m.live), None)
    return ImproveSummary(
        waiting=len(service.inbox(session, project)),
        ready=service.training_pool_count(session, project),
        live_checked=live.checked if live else 0,
        live_right=live.checked_right if live else 0,
    )
