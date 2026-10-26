from typing import Annotated

from fastapi import APIRouter, Depends, File, Response, UploadFile
from sqlalchemy.orm import Session

from system1.auth.deps import get_principal
from system1.auth.principal import Principal
from system1.batch import service
from system1.datasets.constants import UPLOAD_MAX_BYTES
from system1.db import get_session
from system1.generation.router import JobStarted
from system1.ingest.parse import FileTooLarge
from system1.projects.service import get_project
from system1.providers import Providers, get_providers

router = APIRouter(prefix="/projects", dependencies=[Depends(get_principal)])

PrincipalDep = Annotated[Principal, Depends(get_principal)]
SessionDep = Annotated[Session, Depends(get_session)]
ProvidersDep = Annotated[Providers, Depends(get_providers)]


# async so the job starts on the server's event loop.
@router.post("/{project_id}/batches")
async def check_batch(
    project_id: str,
    principal: PrincipalDep,
    session: SessionDep,
    providers: ProvidersDep,
    file: Annotated[UploadFile, File()],
) -> JobStarted:
    """Runs your live model on every row of the file. Unsure answers then wait in the inbox."""
    project = get_project(session, principal, project_id)
    # Read one byte past the limit so an oversized file is rejected without loading all of it.
    data = await file.read(UPLOAD_MAX_BYTES + 1)
    if len(data) > UPLOAD_MAX_BYTES:
        raise FileTooLarge()
    texts, skipped = service.read_texts(file.filename or "batch", data)
    return JobStarted(job_id=service.start_batch(session, providers, principal, project, texts, skipped))


@router.get("/{project_id}/batches/{batch_id}/download")
def download_batch(project_id: str, batch_id: str, principal: PrincipalDep, session: SessionDep) -> Response:
    project = get_project(session, principal, project_id)
    body = service.download(session, principal, project, batch_id)
    return Response(
        content=body,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="batch-{batch_id[:8]}.csv"'},
    )
