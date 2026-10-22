from datetime import datetime

from sqlalchemy import JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from system1.db import Base
from system1.projects.models import new_id, now


class Example(Base):
    """One labelled input the model learns from or is scored on. The test split is frozen at the first training."""

    __tablename__ = "examples"

    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    input_json: Mapped[str | dict] = mapped_column(JSON)
    label: Mapped[str]
    source: Mapped[str]  # uploaded | generated | corrected
    split: Mapped[str]  # train | cal | test
    how_sure: Mapped[float | None] = mapped_column(default=None)
    review: Mapped[str | None] = mapped_column(default=None)  # agree | moved
    dataset_version: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(default=now)
