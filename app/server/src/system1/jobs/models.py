from datetime import datetime

from sqlalchemy import JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from system1.db import Base
from system1.projects.models import new_id, now


class Job(Base):
    """Background work for a project, run by `run_job` inside the server process."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    kind: Mapped[str]  # generation | training
    status: Mapped[str] = mapped_column(default="queued")  # queued | running | succeeded | failed | preview
    progress: Mapped[float] = mapped_column(default=0.0)
    stage: Mapped[str | None] = mapped_column(default=None)
    message: Mapped[str | None] = mapped_column(default=None)
    result_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_at: Mapped[datetime] = mapped_column(default=now)
    finished_at: Mapped[datetime | None] = mapped_column(default=None)
