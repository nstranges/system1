from datetime import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from system1.db import Base
from system1.projects.models import new_id, now


class ContextDoc(Base):
    """A document the user gave us about how their team decides (a handbook, a pasted FAQ). It is data only."""

    __tablename__ = "context_docs"

    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str]
    kind: Mapped[str]  # pdf | docx | md | txt | paste
    text: Mapped[str]
    chars: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(default=now)
