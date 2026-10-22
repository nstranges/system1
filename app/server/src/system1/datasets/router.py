from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from system1.auth.deps import get_principal
from system1.auth.principal import Principal
from system1.datasets import service
from system1.datasets.models import Example
from system1.db import get_session
from system1.projects.service import get_project

router = APIRouter(dependencies=[Depends(get_principal)])

PrincipalDep = Annotated[Principal, Depends(get_principal)]
SessionDep = Annotated[Session, Depends(get_session)]


class ExampleOut(BaseModel):
    id: str
    input: str | dict
    label: str
    source: str
    split: str
    how_sure: float | None
    review: str | None


class ReviewIn(BaseModel):
    action: Literal["agree", "move"]
    to: str | None = None


class DeleteBucketIn(BaseModel):
    mode: Literal["drop", "move"]
    to: str | None = None
    reset_test: bool = False


def _out(example: Example) -> ExampleOut:
    return ExampleOut(
        id=example.id,
        input=example.input_json,
        label=example.label,
        source=example.source,
        split=example.split,
        how_sure=example.how_sure,
        review=example.review,
    )


@router.get("/projects/{project_id}/examples/health")
def examples_health(project_id: str, principal: PrincipalDep, session: SessionDep) -> service.Health:
    return service.health(session, get_project(session, principal, project_id))


@router.get("/projects/{project_id}/examples")
def list_examples(
    project_id: str,
    principal: PrincipalDep,
    session: SessionDep,
    split: Literal["train", "cal", "test"] | None = None,
    source: Literal["uploaded", "generated", "corrected"] | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[ExampleOut]:
    project = get_project(session, principal, project_id)
    return [_out(e) for e in service.list_examples(session, project, split, source, limit)]


@router.get("/projects/{project_id}/review")
def review_queue(project_id: str, principal: PrincipalDep, session: SessionDep) -> list[ExampleOut]:
    return [_out(e) for e in service.review_queue(session, get_project(session, principal, project_id))]


@router.post("/examples/{example_id}/review")
def review_example(example_id: str, body: ReviewIn, principal: PrincipalDep, session: SessionDep) -> ExampleOut:
    _, project = service.get_example(session, principal, example_id)
    return _out(service.review(session, project, example_id, body.action, body.to))


@router.post("/projects/{project_id}/buckets/{key}/delete")
def delete_bucket(
    project_id: str, key: str, body: DeleteBucketIn, principal: PrincipalDep, session: SessionDep
) -> service.DeleteBucketResult:
    project = get_project(session, principal, project_id)
    return service.delete_bucket(session, principal, project, key, body.mode, body.to, body.reset_test)
