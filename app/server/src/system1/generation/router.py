from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from system1.auth.deps import get_principal
from system1.auth.principal import Principal
from system1.config import get_settings
from system1.db import get_session
from system1.generation import service
from system1.projects.service import get_project
from system1.providers import Providers, get_providers

router = APIRouter(prefix="/projects", dependencies=[Depends(get_principal)])

PrincipalDep = Annotated[Principal, Depends(get_principal)]
SessionDep = Annotated[Session, Depends(get_session)]
ProvidersDep = Annotated[Providers, Depends(get_providers)]


class GenerateIn(BaseModel):
    # Examples to write per bucket. Left out, each bucket is filled up to the default target.
    targets: dict[str, int] | None = None


class JobStarted(BaseModel):
    job_id: str


@router.post("/{project_id}/generate/estimate")
def estimate(project_id: str, body: GenerateIn, principal: PrincipalDep, session: SessionDep) -> service.Estimate:
    project = get_project(session, principal, project_id)
    _, targets = service.resolve_targets(session, project, body.targets)
    return service.estimate(targets)


# async so the job starts on the server's event loop; the client calls this only after its confirmation card.
@router.post("/{project_id}/generate")
async def generate(
    project_id: str, body: GenerateIn, principal: PrincipalDep, session: SessionDep, providers: ProvidersDep
) -> JobStarted:
    project = get_project(session, principal, project_id)
    job_id = service.start_generation(session, providers, get_settings(), principal, project, body.targets)
    return JobStarted(job_id=job_id)
