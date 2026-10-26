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
from system1.registry.schemas import ModelOut

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
