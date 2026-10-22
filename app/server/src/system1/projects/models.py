import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from system1.db import Base


def new_id() -> str:
    return uuid.uuid4().hex


def now() -> datetime:
    return datetime.now(UTC)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(index=True)
    name: Mapped[str]
    description: Mapped[str | None] = mapped_column(default=None)
    template_id: Mapped[str | None] = mapped_column(default=None)
    stage: Mapped[str] = mapped_column(default="usecase")
    default_lane: Mapped[str] = mapped_column(default="jev")  # jev | sys1 | auto
    live_model_label: Mapped[str | None] = mapped_column(default=None)
    created_by: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=now)


class PolicyVersion(Base):
    __tablename__ = "policy_versions"
    __table_args__ = (UniqueConstraint("project_id", "version"),)

    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    version: Mapped[int]
    policy_json: Mapped[dict] = mapped_column(JSON)
    created_by: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=now)
