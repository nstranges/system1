from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from system1.auth.deps import get_principal
from system1.auth.principal import Principal
from system1.db import get_session
from system1.errors import ApiError, NotFound
from system1.gateway import keys, service
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


class Forbidden(ApiError):
    status_code = 403
    code = "forbidden"
    message = "Only an admin can do that."


class KeyOut(BaseModel):
    id: str
    prefix: str
    created_at: datetime


class KeyCreated(KeyOut):
    # The only time the full key is ever returned.
    key: str


def _key_out(row: keys.ApiKey) -> KeyOut:
    return KeyOut(id=row.id, prefix=row.prefix, created_at=row.created_at)


@router.get("/{project_id}/keys")
def list_keys(project_id: str, principal: PrincipalDep, session: SessionDep) -> list[KeyOut]:
    project = get_project(session, principal, project_id)
    return [_key_out(k) for k in keys.list_keys(session, project)]


@router.post("/{project_id}/keys")
def create_key(project_id: str, principal: PrincipalDep, session: SessionDep) -> KeyCreated:
    project = get_project(session, principal, project_id)  # 404 for other orgs before the role check
    if principal.org_role != "admin":
        raise Forbidden()
    row, raw = keys.create_key(session, principal, project)
    return KeyCreated(**_key_out(row).model_dump(), key=raw)


@router.delete("/{project_id}/keys/{key_id}", status_code=204)
def revoke_key(project_id: str, key_id: str, principal: PrincipalDep, session: SessionDep) -> Response:
    project = get_project(session, principal, project_id)
    if principal.org_role != "admin":
        raise Forbidden()
    if not keys.revoke_key(session, project, key_id):
        raise NotFound("Key not found.")
    return Response(status_code=204)
