from fastapi.testclient import TestClient

from system1.main import create_app


def test_health_returns_ok():
    assert TestClient(create_app()).get("/api/health").json() == {"status": "ok"}
