import hashlib
import hmac
import secrets
from datetime import datetime

from sqlalchemy import ForeignKey, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from system1.auth.principal import Principal
from system1.db import Base
from system1.projects.models import Project, new_id, now

PREFIX_LEN = 8


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    prefix: Mapped[str] = mapped_column(index=True)  # shown in the list so people can tell keys apart
    hash: Mapped[str]  # sha256 of the key; the plaintext is never stored
    created_by: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(default=now)
    revoked_at: Mapped[datetime | None] = mapped_column(default=None)


def _digest(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def create_key(session: Session, principal: Principal, project: Project) -> tuple[ApiKey, str]:
    """Returns the plaintext key, which exists only in this return value."""
    raw = "s1_" + secrets.token_urlsafe(24)
    row = ApiKey(
        org_id=project.org_id,
        project_id=project.id,
        prefix=raw[:PREFIX_LEN],
        hash=_digest(raw),
        created_by=principal.user_id,
    )
    session.add(row)
    session.commit()
    return row, raw


def resolve_key(session: Session, raw: str) -> ApiKey | None:
    candidates = session.scalars(select(ApiKey).where(ApiKey.prefix == raw[:PREFIX_LEN], ApiKey.revoked_at.is_(None)))
    digest = _digest(raw)
    # Constant-time compare so a response can't leak how much of a hash matched.
    return next((k for k in candidates if hmac.compare_digest(k.hash, digest)), None)


def list_keys(session: Session, project: Project) -> list[ApiKey]:
    stmt = (
        select(ApiKey)
        .where(ApiKey.project_id == project.id, ApiKey.revoked_at.is_(None))
        .order_by(ApiKey.created_at.desc())
    )
    return list(session.scalars(stmt))


def revoke_key(session: Session, project: Project, key_id: str) -> bool:
    row = session.get(ApiKey, key_id)
    if row is None or row.project_id != project.id or row.revoked_at is not None:
        return False
    row.revoked_at = now()
    session.commit()
    return True
