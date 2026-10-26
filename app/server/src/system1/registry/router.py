from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from system1.auth.deps import get_principal
from system1.auth.principal import Principal
from system1.db import get_session
from system1.projects.router import Forbidden
from system1.projects.schemas import ProjectOut
from system1.projects.service import get_project
from system1.registry import service
from system1.registry.schemas import Comparison, ModelOut

router = APIRouter(prefix="/models", dependencies=[Depends(get_principal)])

PrincipalDep = Annotated[Principal, Depends(get_principal)]
SessionDep = Annotated[Session, Depends(get_session)]


@router.get("")
def list_models(principal: PrincipalDep, session: SessionDep, project_id: str | None = None) -> list[ModelOut]:
    if project_id is not None:
        get_project(session, principal, project_id)  # 404 for another org's project
    return service.list_models(session, principal, project_id)


@router.post("/{model_id}/live")
def make_live(model_id: str, principal: PrincipalDep, session: SessionDep) -> ProjectOut:
    """Points the project's sys1 lane at this model. Changing what answers live calls is an admin's call, like keys."""
    service.get_model(session, principal, model_id)  # 404 before 403, so other orgs learn nothing
    if principal.org_role != "admin":
        raise Forbidden()
    project = service.make_live(session, principal, model_id)
    return ProjectOut.model_validate(project, from_attributes=True)


@router.delete("/{model_id}/live")
def turn_off(model_id: str, principal: PrincipalDep, session: SessionDep) -> ProjectOut:
    """Takes this model off the project's endpoint, which then has no live model until one is picked."""
    service.get_model(session, principal, model_id)
    if principal.org_role != "admin":
        raise Forbidden()
    project = service.turn_off(session, principal, model_id)
    return ProjectOut.model_validate(project, from_attributes=True)


@router.delete("/{model_id}")
def delete_model(model_id: str, principal: PrincipalDep, session: SessionDep) -> ProjectOut:
    """Returns the project, since deleting its live model leaves its endpoint with none."""
    service.get_model(session, principal, model_id)
    if principal.org_role != "admin":
        raise Forbidden()
    project = service.delete_model(session, principal, model_id)
    return ProjectOut.model_validate(project, from_attributes=True)


@router.get("/{model_id}/compare")
def compare(model_id: str, principal: PrincipalDep, session: SessionDep) -> Comparison:
    return service.compare(session, principal, model_id)
