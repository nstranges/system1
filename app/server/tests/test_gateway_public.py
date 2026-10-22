from sqlalchemy import select
from sqlalchemy.orm import Session

from system1.adapters.fakes import FakeDecisionProvider, FakeLLM, FakeTrainer
from system1.contracts.decisions import ChoiceAnswer, DecisionRequest, DecisionResponse
from system1.decisions.models import Decision
from system1.providers import Providers

FLAGSHIP = "tallyfern-triage"


class UnsureSys1:
    """A sys1 whose top probability is 0.5, below the auto threshold."""

    name = "sys1"

    async def decide(self, req: DecisionRequest) -> DecisionResponse:
        answers = {}
        for qname, question in req.questions.items():
            options = list(question.get("criteria") or {})
            probs = {options[0]: 0.5, options[1]: 0.5}
            answers[qname] = ChoiceAnswer(type="choice", choice=options[0], probabilities=probs)
        return DecisionResponse(model="sys1-unsure", answers=answers, latency_ms=1.0)


def _project_and_key(client, **patch) -> tuple[str, str]:
    project_id = client.post("/api/projects", json={"name": "P", "template_id": FLAGSHIP}).json()["id"]
    if patch:
        client.patch(f"/api/projects/{project_id}", json=patch)
    created = client.post(f"/api/projects/{project_id}/keys")
    assert created.status_code == 200
    return project_id, created.json()["key"]


def _bearer(key: str) -> dict:
    return {"Authorization": f"Bearer {key}"}


def test_public_decide_with_key_returns_system1_block(client_for):
    client = client_for("org_a")
    project_id, key = _project_and_key(client)
    assert key.startswith("s1_") and len(key) == 35

    res = client.post("/v1/systemone", json={"state": "billing problem"}, headers=_bearer(key))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["model"] == "jev-fake"
    assert body["answers"]
    block = body["system1"]
    assert set(block) == {"decision_id", "routed_to", "policy_version", "latency_ms"}
    assert block["policy_version"] == 1

    with Session(client.app.state.engine) as session:
        decision = session.get(Decision, block["decision_id"])
        assert decision is not None
        assert (decision.project_id, decision.source) == (project_id, "api")

    # The key is hashed at rest: the app list shows a prefix, never the key or its hash.
    listed = client.get(f"/api/projects/{project_id}/keys").json()
    assert listed[0]["prefix"] == key[:8]
    assert key not in str(listed) and "hash" not in listed[0]

    feedback = client.post(
        "/v1/feedback",
        json={"decision_id": block["decision_id"], "correct": {"queue": "billing"}},
        headers=_bearer(key),
    )
    assert feedback.status_code == 200


def test_revoked_key_gets_401(client_for):
    client = client_for("org_a")
    project_id, key = _project_and_key(client)
    key_id = client.get(f"/api/projects/{project_id}/keys").json()[0]["id"]
    assert client.delete(f"/api/projects/{project_id}/keys/{key_id}").status_code == 204

    for headers in (_bearer(key), {}, _bearer("s1_nope")):
        res = client.post("/v1/systemone", json={"state": "hi"}, headers=headers)
        assert res.status_code == 401


def test_key_for_project_a_cannot_decide_for_project_b(client_for):
    client = client_for("org_a")
    _, key_a = _project_and_key(client)
    project_b = client.post("/api/projects", json={"name": "B", "template_id": FLAGSHIP}).json()["id"]

    res = client.post(
        "/v1/systemone", json={"state": "hi", "project": project_b, "project_id": project_b}, headers=_bearer(key_a)
    )
    assert res.status_code == 200
    with Session(client.app.state.engine) as session:
        decision = session.scalars(select(Decision).where(Decision.id == res.json()["system1"]["decision_id"])).one()
        assert decision.project_id != project_b

    # Another org cannot mint or list keys for this project.
    other = client_for("org_b", engine=client.app.state.engine)
    assert other.post(f"/api/projects/{project_b}/keys").status_code == 404
    assert other.get(f"/api/projects/{project_b}/keys").status_code == 404


def test_auto_falls_back_to_jev_and_flags_review_when_sys1_unsure(client_for):
    providers = Providers(
        jev=FakeDecisionProvider("jev", "jev-fake"), sys1=UnsureSys1(), llm=FakeLLM([]), trainer=FakeTrainer()
    )
    client = client_for("org_a", providers=providers)
    _, key = _project_and_key(client, default_lane="auto")

    res = client.post("/v1/systemone", json={"state": "billing problem"}, headers=_bearer(key))
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["model"] == "jev-fake" and body["system1"]["routed_to"] == "jev-fake"
    with Session(client.app.state.engine) as session:
        decision = session.get(Decision, body["system1"]["decision_id"])
        assert decision is not None and decision.needs_review and decision.lane == "jev"
