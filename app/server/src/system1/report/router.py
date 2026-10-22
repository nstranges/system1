from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from system1.auth.deps import get_principal
from system1.auth.principal import Principal
from system1.config import get_settings
from system1.db import get_session
from system1.generation.router import JobStarted
from system1.projects.service import get_project
from system1.providers import Providers, get_providers
from system1.report import service
from system1.report.schemas import Report

router = APIRouter(prefix="/projects", dependencies=[Depends(get_principal)])

PrincipalDep = Annotated[Principal, Depends(get_principal)]
SessionDep = Annotated[Session, Depends(get_session)]
ProvidersDep = Annotated[Providers, Depends(get_providers)]


# async so the job starts on the server's event loop; the client calls this only after its confirmation card.
@router.post("/{project_id}/training")
async def train(project_id: str, principal: PrincipalDep, session: SessionDep, providers: ProvidersDep) -> JobStarted:
    project = get_project(session, principal, project_id)
    return JobStarted(job_id=service.start_training(session, providers, get_settings(), principal, project))


@router.get("/{project_id}/report")
def get_report(project_id: str, principal: PrincipalDep, session: SessionDep) -> Report:
    return service.report(session, get_project(session, principal, project_id))
