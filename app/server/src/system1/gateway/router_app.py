from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from system1.auth.deps import get_principal
from system1.auth.principal import Principal
from system1.db import get_session
from system1.gateway import service
from system1.gateway.service import TryResult
from system1.projects.schemas import SampleOut, TryIn
from system1.projects.service import get_project
from system1.providers import Providers, get_providers

router = APIRouter(prefix="/projects", dependencies=[Depends(get_principal)])

PrincipalDep = Annotated[Principal, Depends(get_principal)]
SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/{project_id}/samples")
def samples(project_id: str, principal: PrincipalDep, session: SessionDep) -> list[SampleOut]:
    project = get_project(session, principal, project_id)
    # Gold labels and rule ids stay server-side until the Try result reveals them.
    return [SampleOut(id=r.id, state=r.state) for r in service.flagship_rows(project)]


@router.post("/{project_id}/try")
async def try_it(
    project_id: str,
    body: TryIn,
    principal: PrincipalDep,
    session: SessionDep,
    providers: Annotated[Providers, Depends(get_providers)],
) -> TryResult:
    project = get_project(session, principal, project_id)
    return await service.try_input(session, providers, project, body.text, body.sample_id)
