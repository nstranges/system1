from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from system1.auth.deps import get_principal
from system1.auth.principal import Principal
from system1.context import service
from system1.context.extract import MAX_NAME_CHARS, extract_text
from system1.context.models import ContextDoc
from system1.datasets.constants import CONTEXT_MAX_FILE_BYTES
from system1.db import get_session
from system1.projects.service import get_project

router = APIRouter(dependencies=[Depends(get_principal)])

PrincipalDep = Annotated[Principal, Depends(get_principal)]
SessionDep = Annotated[Session, Depends(get_session)]


class ContextDocOut(BaseModel):
    id: str
    name: str
    kind: str
    chars: int
    created_at: datetime


class PasteIn(BaseModel):
    name: str = Field(default="Pasted text", max_length=MAX_NAME_CHARS)
    text: str


def _out(doc: ContextDoc) -> ContextDocOut:
    return ContextDocOut.model_validate(doc, from_attributes=True)


@router.get("/projects/{project_id}/context")
def list_context(project_id: str, principal: PrincipalDep, session: SessionDep) -> list[ContextDocOut]:
    project = get_project(session, principal, project_id)
    return [_out(d) for d in service.list_docs(session, principal, project)]


@router.post("/projects/{project_id}/context")
def upload_context(
    project_id: str, principal: PrincipalDep, session: SessionDep, file: Annotated[UploadFile, File()]
) -> ContextDocOut:
    project = get_project(session, principal, project_id)
    # Read one byte past the limit so an oversized file is rejected without loading all of it.
    data = file.file.read(CONTEXT_MAX_FILE_BYTES + 1)
    if len(data) > CONTEXT_MAX_FILE_BYTES:
        raise service.FileTooLarge()
    name = file.filename or "upload"
    kind, text = extract_text(name, data)
    return _out(service.add_doc(session, project, principal, name, kind, text))


@router.post("/projects/{project_id}/context/paste")
def paste_context(project_id: str, body: PasteIn, principal: PrincipalDep, session: SessionDep) -> ContextDocOut:
    project = get_project(session, principal, project_id)
    if len(body.text) > CONTEXT_MAX_FILE_BYTES:
        raise service.FileTooLarge("That text is over 2 MB.")
    return _out(service.add_doc(session, project, principal, body.name, "paste", body.text))


@router.delete("/projects/{project_id}/context/{doc_id}", status_code=204)
def delete_context(project_id: str, doc_id: str, principal: PrincipalDep, session: SessionDep) -> Response:
    project = get_project(session, principal, project_id)
    service.delete_doc(session, principal, project, doc_id)
    return Response(status_code=204)
