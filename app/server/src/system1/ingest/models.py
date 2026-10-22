from datetime import datetime

from sqlalchemy import JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from system1.db import Base
from system1.projects.models import new_id, now


class StagedUpload(Base):
    """A parsed upload waiting for the user to map its columns. It expires after an hour."""

    __tablename__ = "staged_uploads"

    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    rows_json: Mapped[dict] = mapped_column(JSON)  # {"columns": [...], "rows": [{column: value}, ...]}
    created_at: Mapped[datetime] = mapped_column(default=now)
