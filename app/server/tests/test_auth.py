import pytest
from fastapi.testclient import TestClient

from system1.auth.principal import NoActiveOrganization, Principal, principal_from_claims
from system1.auth.verifier import FakeVerifier
from system1.db import make_engine
from system1.main import create_app


def test_claims_with_org_give_principal():
    claims = {"sub": "user_1", "o": {"id": "org_a", "rol": "admin", "slg": "acme"}}
    assert principal_from_claims(claims) == Principal("user_1", "org_a", "admin", "acme")


def test_pending_session_has_no_org():
    with pytest.raises(NoActiveOrganization):
        principal_from_claims({"sub": "user_1", "sts": "pending"})


def test_api_without_org_returns_403_no_active_org(client_for):
    response = client_for(None).get("/api/me")
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "no_active_org"


def test_api_without_token_returns_401():
    app = create_app(verifier=FakeVerifier(None), engine=make_engine("sqlite:///:memory:"))
    response = TestClient(app).get("/api/me")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "unauthenticated"
