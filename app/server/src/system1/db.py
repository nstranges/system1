from collections.abc import Iterator
from pathlib import Path

from fastapi import Request
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


def make_engine(url: str) -> Engine:
    parsed = make_url(url)
    in_memory = parsed.get_backend_name() == "sqlite" and parsed.database in (None, "", ":memory:")
    kwargs: dict = {}
    if parsed.get_backend_name() == "sqlite":
        if in_memory:
            # One shared connection, or each thread would see its own empty database.
            kwargs = {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
        else:
            Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, **kwargs)
    if parsed.get_backend_name() == "sqlite" and not in_memory:

        @event.listens_for(engine, "connect")
        def _wal(dbapi_connection, _):
            dbapi_connection.execute("PRAGMA journal_mode=WAL")

    return engine


def init_db(engine: Engine) -> None:
    # Import so every table module has registered with Base before create_all.
    from system1 import usage  # noqa: F401

    Base.metadata.create_all(engine)


def get_session(request: Request) -> Iterator[Session]:
    with Session(request.app.state.engine) as session:
        yield session
