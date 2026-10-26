from datetime import datetime

from sqlalchemy import JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from system1.db import Base
from system1.projects.models import new_id, now


class ReportCard(Base):
    """One scored training run. It records the test set it was scored on, so cards compare only on the same one."""

    __tablename__ = "report_cards"

    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    job_id: Mapped[str | None] = mapped_column(default=None)
    test_set_version: Mapped[int]
    policy_version: Mapped[int]
    dataset_version: Mapped[int]
    rows_json: Mapped[list] = mapped_column(JSON)
    verdict_json: Mapped[dict] = mapped_column(JSON)
    details_json: Mapped[dict] = mapped_column(JSON)
    is_preview: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=now)


class JevEval(Base):
    """Jev's answers on a project's test examples, kept so the same test set and guidelines are only paid for once."""

    __tablename__ = "jev_evals"
    __table_args__ = (UniqueConstraint("project_id", "test_set_version", "policy_version", "lane"),)

    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    test_set_version: Mapped[int]
    policy_version: Mapped[int]
    lane: Mapped[str]  # "jev:<hash of the question asked>" or "jev_labels:<hash>"
    # example id -> {"label", "p_gold", "latency_ms"}. Examples Jev failed on are left out, so a rerun retries them.
    results_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(default=now)
