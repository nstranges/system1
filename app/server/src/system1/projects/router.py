from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from system1.auth.deps import get_principal
from system1.auth.principal import Principal
from system1.db import get_session
from system1.domain.policy import validate_policy
from system1.errors import ApiError
from system1.projects import service
from system1.projects.schemas import (
    PolicyIn,
    PolicyOut,
    ProjectCreate,
    ProjectOut,
    ProjectPatch,
    TemplateOut,
)
from system1.templates.catalog import load_templates

router = APIRouter(dependencies=[Depends(get_principal)])

PrincipalDep = Annotated[Principal, Depends(get_principal)]
SessionDep = Annotated[Session, Depends(get_session)]


class Forbidden(ApiError):
    status_code = 403
    code = "forbidden"
    message = "Only an admin can do that."


def _out(project) -> ProjectOut:
    return ProjectOut.model_validate(project, from_attributes=True)


@router.get("/templates")
def templates() -> list[TemplateOut]:
    return [
        TemplateOut(
            **t.model_dump(include=set(TemplateOut.model_fields) - {"flagship"}), flagship=t.flagship is not None
        )
        for t in load_templates()
    ]


@router.get("/projects")
def list_projects(principal: PrincipalDep, session: SessionDep) -> list[ProjectOut]:
    return [_out(p) for p in service.list_projects(session, principal)]


@router.post("/projects")
def create_project(body: ProjectCreate, principal: PrincipalDep, session: SessionDep) -> ProjectOut:
    return _out(service.create_project(session, principal, body.name, body.template_id, body.description))


@router.get("/projects/{project_id}")
def get_project(project_id: str, principal: PrincipalDep, session: SessionDep) -> ProjectOut:
    return _out(service.get_project(session, principal, project_id))


@router.patch("/projects/{project_id}")
def patch_project(project_id: str, body: ProjectPatch, principal: PrincipalDep, session: SessionDep) -> ProjectOut:
    project = service.get_project(session, principal, project_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(project, field, value)
    session.commit()
    return _out(project)


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: str, principal: PrincipalDep, session: SessionDep) -> Response:
    service.get_project(session, principal, project_id)  # 404 for other orgs before the role check
    if principal.org_role != "admin":
        raise Forbidden()
    service.delete_project(session, principal, project_id)
    return Response(status_code=204)


@router.get("/projects/{project_id}/policy")
def get_policy(project_id: str, principal: PrincipalDep, session: SessionDep) -> PolicyOut:
    project = service.get_project(session, principal, project_id)
    service.ensure_policy(session, principal, project)
    policy, version = service.current_policy(session, principal, project)
    return PolicyOut(policy=policy, version=version, issues=validate_policy(policy))


@router.put("/projects/{project_id}/policy")
def put_policy(project_id: str, body: PolicyIn, principal: PrincipalDep, session: SessionDep) -> PolicyOut:
    project = service.get_project(session, principal, project_id)
    version = service.save_policy(session, principal, project, body.policy)
    return PolicyOut(policy=body.policy, version=version, issues=[])
