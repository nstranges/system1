from collections.abc import Iterator
from pathlib import Path

from fastapi import Request
from sqlalchemy import Engine, create_engine, event, inspect, text
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
    from system1.agent import models as agent_models  # noqa: F401
    from system1.context import models as context_models  # noqa: F401
    from system1.datasets import models as dataset_models  # noqa: F401
    from system1.decisions import models as decision_models  # noqa: F401
    from system1.gateway import keys  # noqa: F401
    from system1.ingest import models as ingest_models  # noqa: F401
    from system1.jobs import models as job_models  # noqa: F401
    from system1.projects import models as project_models  # noqa: F401

    Base.metadata.create_all(engine)
    for table in ("feedback", "projects"):
        _add_missing_columns(engine, table)


def _add_missing_columns(engine: Engine, table: str) -> None:
    """There are no migrations: a dev database made before a column existed gets it added here (SQLite)."""
    if engine.dialect.name != "sqlite":
        return
    spec = Base.metadata.tables[table]
    have = {c["name"] for c in inspect(engine).get_columns(table)}
    with engine.begin() as conn:
        for col in spec.columns:
            if col.name in have:
                continue
            ddl = f"ALTER TABLE {table} ADD COLUMN {col.name} {col.type.compile(engine.dialect)}"
            # Only constant defaults can be written into DDL; a callable default has no value to put there.
            if col.default is not None and col.default.is_scalar and not col.nullable:
                value = col.default.arg
                ddl += f" NOT NULL DEFAULT {int(value) if isinstance(value, bool) else repr(value)}"
            conn.execute(text(ddl))


def get_session(request: Request) -> Iterator[Session]:
    with Session(request.app.state.engine) as session:
        yield session
