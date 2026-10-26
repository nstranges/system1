from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from system1.auth.deps import get_principal
from system1.auth.principal import Principal
from system1.db import get_session
from system1.jobs import service
from system1.jobs.models import Job

router = APIRouter(dependencies=[Depends(get_principal)])

PrincipalDep = Annotated[Principal, Depends(get_principal)]
SessionDep = Annotated[Session, Depends(get_session)]


class JobOut(BaseModel):
    id: str
    project_id: str
    kind: str
    status: str
    progress: float
    stage: str | None
    message: str | None
    result: dict | None
    created_at: datetime
    finished_at: datetime | None


def _out(job: Job) -> JobOut:
    return JobOut(**{f: getattr(job, f) for f in JobOut.model_fields if f != "result"}, result=job.result_json)


@router.get("/jobs/{job_id}")
def get_job(job_id: str, principal: PrincipalDep, session: SessionDep) -> JobOut:
    return _out(service.get_job(session, principal, job_id))


# async so the stop request reaches the job's task on the event loop it runs on.
@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str, principal: PrincipalDep, session: SessionDep) -> JobOut:
    return _out(service.cancel_job(session, principal, job_id))
