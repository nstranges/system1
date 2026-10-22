from collections.abc import Callable, Iterator
from contextlib import ExitStack

import pytest
from fastapi.testclient import TestClient

from system1.adapters.fakes import FakeDecisionProvider, FakeLLM, FakeTrainer
from system1.auth.verifier import FakeVerifier
from system1.db import make_engine
from system1.main import create_app
from system1.providers import Providers


@pytest.fixture
def client_for() -> Iterator[Callable[..., TestClient]]:
    """Build a client signed in as `user_id` in `org_id` (None means no active organization)."""
    stack = ExitStack()

    def build(org_id: str | None, user_id: str = "user_1", providers: Providers | None = None) -> TestClient:
        claims: dict = {"sub": user_id}
        if org_id is None:
            claims["sts"] = "pending"
        else:
            claims["o"] = {"id": org_id, "rol": "admin", "slg": org_id}
        providers = providers or Providers(
            jev=FakeDecisionProvider("jev", "jev-fake"),
            sys1=FakeDecisionProvider("sys1", "sys1-fake"),
            llm=FakeLLM([]),
            trainer=FakeTrainer(),
        )
        app = create_app(verifier=FakeVerifier(claims), engine=make_engine("sqlite:///:memory:"), providers=providers)
        return stack.enter_context(TestClient(app))

    with stack:
        yield build
