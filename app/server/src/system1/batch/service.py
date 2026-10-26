import csv
import io
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from system1.auth.principal import Principal
from system1.config import get_settings
from system1.decisions.models import Decision
from system1.decisions.service import guesses, margin
from system1.errors import ApiError, NotFound
from system1.gateway.service import run_batch, sys1_ready
from system1.ingest.parse import parse_table
from system1.jobs import service as job_service
from system1.jobs.service import JobContext
from system1.projects.models import Project
from system1.providers import Providers

BATCH_MAX_ROWS = 1000
# Column names that usually hold the text to decide on, tried in order before falling back to the first column.
TEXT_COLUMNS = ("text", "message", "input", "body", "ticket", "content", "description")
# Below this gap between the top two answers, an answer counts as unsure (the inbox's "Not sure").
UNSURE_MARGIN = 0.2
TOP_SHOWN = 5


class BatchNotReady(ApiError):
    status_code = 422
    code = "batch_not_ready"
    message = "This project has no live model yet. Train one, then check a batch."


class BatchUnreadable(ApiError):
    status_code = 422
    code = "batch_unreadable"
    message = "That file has no rows to check."


def read_texts(filename: str, data: bytes) -> tuple[list[str], int]:
    """The text of each row, and how many rows were skipped as empty or over the length limit."""
    table = parse_table(filename, data)
    if not table.columns or not table.rows:
        raise BatchUnreadable()
    by_name = {c.strip().lower(): c for c in table.columns}
    column = next((by_name[n] for n in TEXT_COLUMNS if n in by_name), table.columns[0])
    limit = get_settings().max_input_chars
    texts, skipped = [], 0
    for row in table.rows:
        text = (row.get(column) or "").strip()
        if not text or len(text) > limit:
            skipped += 1
        else:
            texts.append(text)
    if not texts:
        raise BatchUnreadable()
    if len(texts) > BATCH_MAX_ROWS:
        raise BatchUnreadable(f"A batch can have at most {BATCH_MAX_ROWS:,} rows. This one has {len(texts):,}.")
    return texts, skipped


def summarize(decisions: list[Decision]) -> dict:
    unsure = sum(margin(d) < UNSURE_MARGIN for d in decisions)
    top = Counter(d.top_label for d in decisions if d.top_label).most_common(TOP_SHOWN)
    return {"answered": len(decisions), "unsure": unsure, "top": [{"key": k, "count": n} for k, n in top]}


def start_batch(
    session: Session, providers: Providers, principal: Principal, project: Project, texts: list[str], skipped: int
) -> str:
    """Starts the job and returns its id, which is also the batch id. Call it from the event loop thread."""
    if not sys1_ready(session, providers, project):
        raise BatchNotReady()
    job = job_service.create_job(session, principal, project.id, "batch")
    project_id, batch_id = project.id, job.id

    async def work(ctx: JobContext) -> dict:
        own = ctx.session.get(Project, project_id)
        if own is None:  # deleted while it ran
            return {}
        decisions, failed = await run_batch(
            ctx.session, providers, own, texts, batch_id, on_progress=lambda share: ctx.progress(share, "checking")
        )
        if failed:
            ctx.message = f"Your model didn't answer {failed} of {len(texts)} rows."
        return {"batch_id": batch_id, "failed": failed, "skipped": skipped, **summarize(decisions)}

    job_service.start_job(job_service.session_factory_for(session), job.id, work)
    return job.id


def download(session: Session, principal: Principal, project: Project, batch_id: str) -> str:
    """The batch as CSV: each text with your model's answer, how sure it was and its runner-up."""
    rows = session.scalars(
        select(Decision)
        .where(Decision.project_id == project.id, Decision.org_id == principal.org_id, Decision.batch_id == batch_id)
        .order_by(Decision.created_at, Decision.id)
    ).all()
    if not rows:
        raise NotFound("Batch not found.")
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["text", "answer", "probability", "how_sure", "runner_up"])
    for d in rows:
        top = guesses(d)
        runner_up = top[1][0] if len(top) > 1 else ""
        writer.writerow([d.state_json, d.top_label or "", f"{d.top_prob or 0:.3f}", f"{margin(d):.3f}", runner_up])
    return out.getvalue()
