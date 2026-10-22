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

router = APIRouter(dependencies=[Depends(get_principal)])

PrincipalDep = Annotated[Principal, Depends(get_principal)]
SessionDep = Annotated[Session, Depends(get_session)]


class FeedbackIn(BaseModel):
    kind: Literal["confirm", "correction"]
    correct_label: str | None = None


class FeedbackOut(BaseModel):
    status: str = "recorded"


class InboxItem(BaseModel):
    decision_id: str
    state: str | dict | list
    answer: str | None
    lane: str
    created_at: datetime


class InboxOut(BaseModel):
    items: list[InboxItem]


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
            InboxItem(decision_id=d.id, state=d.state_json, answer=d.top_label, lane=d.lane, created_at=d.created_at)
            for d in service.inbox(session, project)
        ]
    )


@router.get("/projects/{project_id}/training-pool")
def get_training_pool(project_id: str, principal: PrincipalDep, session: SessionDep) -> PoolOut:
    project = get_project(session, principal, project_id)
    return PoolOut(count=service.training_pool_count(session, project))
