import asyncio
import logging
import threading
from collections.abc import Awaitable, Callable

from sqlalchemy.orm import Session, sessionmaker

from system1.auth.principal import Principal
from system1.contracts.decisions import ProviderError
from system1.errors import ApiError, NotFound
from system1.jobs.models import Job
from system1.projects.models import now

log = logging.getLogger(__name__)

SessionFactory = Callable[[], Session]

UNEXPECTED_FAILURE = "Something went wrong on our side. Anything already saved was kept. Try again in a minute."

# The event loop only keeps weak references to tasks, so a running job must be held here.
_tasks: set[asyncio.Task] = set()
# Set when a job ends, whichever thread or event loop is asking, so tests can wait without polling.
_finished: dict[str, threading.Event] = {}


class JobContext:
    """What a running job's code can do: report progress and keep a partial result if it fails."""

    def __init__(self, session: Session, job_id: str):
        self.session = session
        self._job_id = job_id
        self.result: dict | None = None

    def progress(self, value: float, stage: str | None = None) -> None:
        job = self.session.get(Job, self._job_id)
        if job is not None:
            job.progress = max(0.0, min(1.0, value))
            if stage is not None:
                job.stage = stage
            self.session.commit()


JobWork = Callable[[JobContext], Awaitable[dict | None]]


def session_factory_for(session: Session) -> SessionFactory:
    """Sessions on the same database as `session`, for work that outlives the request that started it."""
    return sessionmaker(bind=session.get_bind(), expire_on_commit=True)


def create_job(session: Session, principal: Principal, project_id: str, kind: str) -> Job:
    job = Job(org_id=principal.org_id, project_id=project_id, kind=kind)
    session.add(job)
    session.commit()
    return job


def get_job(session: Session, principal: Principal, job_id: str) -> Job:
    job = session.get(Job, job_id)
    if job is None or job.org_id != principal.org_id:
        raise NotFound("Job not found.")
    return job


def _failure_message(exc: Exception) -> str:
    if isinstance(exc, ProviderError):
        return exc.user_message
    if isinstance(exc, ApiError):
        return exc.message
    log.exception("job failed", exc_info=exc)
    return UNEXPECTED_FAILURE


def _finish(session: Session, job_id: str, status: str, message: str | None, result: dict | None) -> None:
    session.rollback()
    job = session.get(Job, job_id)
    if job is None:  # its project was deleted while it ran
        return
    job.status = status
    job.message = message
    if result is not None:
        job.result_json = result
    if status == "succeeded":
        job.progress = 1.0
    job.finished_at = now()
    session.commit()


async def run_job(session_factory: SessionFactory, job_id: str, work: JobWork) -> None:
    """Runs `work` with its own session and records how it ended. Never raises."""
    try:
        with session_factory() as session:
            job = session.get(Job, job_id)
            if job is None:
                return
            job.status = "running"
            session.commit()
            ctx = JobContext(session, job_id)
            try:
                result = await work(ctx)
            except Exception as exc:  # noqa: BLE001 - job boundary: nothing awaits this task, so any failure must be recorded on the job
                _finish(session, job_id, "failed", _failure_message(exc), ctx.result)
            else:
                _finish(session, job_id, "succeeded", None, result)
    except Exception:
        log.exception("job %s could not be recorded", job_id)
    finally:
        _finished.setdefault(job_id, threading.Event()).set()


def start_job(session_factory: SessionFactory, job_id: str, work: JobWork) -> None:
    """Needs a running event loop: call it from async code."""
    _finished.setdefault(job_id, threading.Event())
    task = asyncio.get_running_loop().create_task(run_job(session_factory, job_id, work))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


def wait_for_job(job_id: str, timeout: float = 10.0) -> None:
    """Blocks until the job ends. For tests: it never returns early and never polls."""
    event = _finished.get(job_id)
    if event is None or not event.wait(timeout):
        raise TimeoutError(f"job {job_id} did not finish")
