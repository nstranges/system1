from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Mapped, Session, mapped_column

from system1.config import get_settings
from system1.db import Base
from system1.errors import ApiError


class BudgetExceeded(ApiError):
    status_code = 429
    code = "budget_exceeded"
    message = "Your team has used today's AI budget. It resets at midnight UTC."


class TokenUsage(Base):
    __tablename__ = "token_usage"

    org_id: Mapped[str] = mapped_column(primary_key=True)
    day: Mapped[date] = mapped_column(primary_key=True)
    tokens: Mapped[int] = mapped_column(default=0)


def _today() -> date:
    return datetime.now(UTC).date()


def record_usage(session: Session, org_id: str, tokens: int) -> None:
    row = session.get(TokenUsage, (org_id, _today()))
    if row is None:
        session.add(TokenUsage(org_id=org_id, day=_today(), tokens=tokens))
    else:
        row.tokens += tokens
    session.commit()


def check_budget(session: Session, org_id: str) -> None:
    used = session.scalar(select(TokenUsage.tokens).where(TokenUsage.org_id == org_id, TokenUsage.day == _today()))
    if (used or 0) >= get_settings().org_daily_token_cap:
        raise BudgetExceeded()
