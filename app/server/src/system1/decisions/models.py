from datetime import datetime

from sqlalchemy import JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from system1.db import Base
from system1.projects.models import new_id, now


class Decision(Base):
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    source: Mapped[str]  # playground | api | agent
    lane: Mapped[str]  # jev | jev_labels | sys1
    model_reported: Mapped[str]
    state_json: Mapped[str | dict | list] = mapped_column(JSON)
    answers_json: Mapped[dict] = mapped_column(JSON)
    top_label: Mapped[str | None]
    top_prob: Mapped[float | None]
    latency_ms: Mapped[float]
    input_tokens: Mapped[int | None] = mapped_column(default=None)
    policy_version: Mapped[int]
    # Jev outputs must never become training labels (TypeSafe agreement), so they are flagged at write time.
    not_for_training: Mapped[bool] = mapped_column(default=False)
    needs_review: Mapped[bool] = mapped_column(default=False)
    dataset_row_id: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(default=now)
