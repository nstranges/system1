from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from system1.auth.deps import get_principal
from system1.auth.principal import Principal
from system1.datasets.constants import UPLOAD_MAX_BYTES
from system1.db import get_session
from system1.ingest import service
from system1.ingest.parse import FileTooLarge
from system1.ingest.service import ImportMapping, ImportResult, Staged
from system1.projects.service import get_project

router = APIRouter(dependencies=[Depends(get_principal)])

PrincipalDep = Annotated[Principal, Depends(get_principal)]
SessionDep = Annotated[Session, Depends(get_session)]


class LabelCount(BaseModel):
    value: str
    count: int


class LabelCounts(BaseModel):
    column: str
    # A list, not an object: labels like "1" and "2" would otherwise be reordered by JavaScript.
    values: list[LabelCount]


@router.post("/projects/{project_id}/uploads")
def upload_examples(
    project_id: str, principal: PrincipalDep, session: SessionDep, file: Annotated[UploadFile, File()]
) -> Staged:
    project = get_project(session, principal, project_id)
    # Read one byte past the limit so an oversized file is rejected without loading all of it.
    data = file.file.read(UPLOAD_MAX_BYTES + 1)
    if len(data) > UPLOAD_MAX_BYTES:
        raise FileTooLarge()
    return service.stage_upload(session, project, principal, file.filename or "upload", data)


@router.get("/projects/{project_id}/uploads/{upload_id}/labels")
def upload_labels(
    project_id: str, upload_id: str, column: str, principal: PrincipalDep, session: SessionDep
) -> LabelCounts:
    project = get_project(session, principal, project_id)
    counts = service.preview_labels(session, project, upload_id, column)
    return LabelCounts(column=column, values=[LabelCount(value=v, count=n) for v, n in counts.items()])


@router.post("/projects/{project_id}/uploads/{upload_id}/import")
def import_examples(
    project_id: str, upload_id: str, body: ImportMapping, principal: PrincipalDep, session: SessionDep
) -> ImportResult:
    project = get_project(session, principal, project_id)
    return service.import_upload(session, project, principal, upload_id, body)
