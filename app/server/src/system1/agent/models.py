from datetime import datetime

from sqlalchemy import JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from system1.db import Base
from system1.projects.models import new_id, now


class AgentTurn(Base):
    """One message in the conversation with the model. Append-only: earlier rows are never edited, so the
    history replays to the API unchanged and prompt caching keeps working."""

    __tablename__ = "agent_turns"
    __table_args__ = (UniqueConstraint("project_id", "seq"),)

    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    org_id: Mapped[str] = mapped_column(index=True)
    seq: Mapped[int]
    role: Mapped[str]  # user | assistant | system
    # Content exactly as sent to / returned by the API: a string or a list of content blocks.
    api_content_json: Mapped[str | list] = mapped_column(JSON)
    # What the UI shows for this turn, so the history endpoint doesn't have to reverse-engineer blocks.
    ui_events_json: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(default=now)


class PendingAction(Base):
    """Paid work the agent proposed. Nothing runs until the user confirms."""

    __tablename__ = "pending_actions"

    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    org_id: Mapped[str] = mapped_column(index=True)
    kind: Mapped[str]  # dataset | training
    params_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(default="pending")  # pending | confirmed | cancelled
    created_at: Mapped[datetime] = mapped_column(default=now)
