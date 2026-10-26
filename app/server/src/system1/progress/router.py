from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from system1.auth.deps import get_principal
from system1.auth.principal import Principal
from system1.db import get_session
from system1.progress import service
from system1.progress.schemas import ProjectProgress
from system1.projects.service import get_project

router = APIRouter(prefix="/projects", dependencies=[Depends(get_principal)])

PrincipalDep = Annotated[Principal, Depends(get_principal)]
SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/{project_id}/progress")
def get_progress(project_id: str, principal: PrincipalDep, session: SessionDep) -> ProjectProgress:
    return service.progress(session, get_project(session, principal, project_id))
