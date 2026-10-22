from sqlalchemy import select
from sqlalchemy.orm import Session

from system1.decisions.models import Decision
from system1.domain.policy import Policy

FLAGSHIP = "tallyfern-triage"


def _policy_body(client, project_id: str) -> dict:
    return client.get(f"/api/projects/{project_id}/policy").json()["policy"]


def test_project_from_template_gets_policy_v1(client_for):
    client = client_for("org_a")
    created = client.post("/api/projects", json={"name": "Triage", "template_id": FLAGSHIP})
    assert created.status_code == 200
    project = created.json()
    assert project["stage"] == "usecase" and project["default_lane"] == "jev"

    got = client.get(f"/api/projects/{project['id']}/policy").json()
    assert got["version"] == 1
    assert got["issues"] == []
    Policy(**got["policy"])
    assert [p["id"] for p in client.get("/api/projects").json()] == [project["id"]]


def test_other_org_gets_404_for_project_and_policy(client_for):
    owner = client_for("org_a")
    project_id = owner.post("/api/projects", json={"name": "Mine", "template_id": FLAGSHIP}).json()["id"]
    other = client_for("org_b", engine=owner.app.state.engine)

    assert other.get("/api/projects").json() == []
    for method, path in [
        ("get", f"/api/projects/{project_id}"),
        ("get", f"/api/projects/{project_id}/policy"),
        ("get", f"/api/projects/{project_id}/samples"),
        ("delete", f"/api/projects/{project_id}"),
    ]:
        assert getattr(other, method)(path).status_code == 404, path
    body = {"policy": _policy_body(owner, project_id)}
    assert other.put(f"/api/projects/{project_id}/policy", json=body).status_code == 404
    assert other.post(f"/api/projects/{project_id}/try", json={"text": "hi"}).status_code == 404


def test_invalid_policy_put_returns_422_and_keeps_old_version(client_for):
    client = client_for("org_a")
    project_id = client.post("/api/projects", json={"name": "P", "template_id": FLAGSHIP}).json()["id"]
    bad = _policy_body(client, project_id)
    bad["options"] = bad["options"][:1]

    res = client.put(f"/api/projects/{project_id}/policy", json={"policy": bad})
    assert res.status_code == 422
    detail = res.json()["detail"]
    assert detail["code"] == "policy_invalid" and detail["issues"]

    kept = client.get(f"/api/projects/{project_id}/policy").json()
    assert kept["version"] == 1
    assert len(kept["policy"]["options"]) > 1


def test_try_returns_both_jev_lanes_and_logs_not_for_training(client_for):
    client = client_for("org_a")
    project_id = client.post("/api/projects", json={"name": "P", "template_id": FLAGSHIP}).json()["id"]

    samples = client.get(f"/api/projects/{project_id}/samples").json()
    assert samples and set(samples[0]) == {"id", "state"}

    res = client.post(f"/api/projects/{project_id}/try", json={"sample_id": samples[0]["id"]})
    assert res.status_code == 200
    body = res.json()
    lanes = {r["lane"]: r for r in body["results"]}
    assert {"jev", "jev_labels"} <= set(lanes)
    assert all(r["error"] is None and r["label"] for r in lanes.values())
    assert body["gold"] and body["rule_id"]

    with Session(client.app.state.engine) as session:
        rows = session.scalars(select(Decision)).all()
    assert len(rows) == len(body["results"])
    assert all(d.not_for_training == d.lane.startswith("jev") for d in rows)
    assert all(d.source == "playground" and d.dataset_row_id == samples[0]["id"] for d in rows)


def test_try_rejects_oversized_input_with_limit_message(client_for):
    client = client_for("org_a")
    project_id = client.post("/api/projects", json={"name": "P", "template_id": FLAGSHIP}).json()["id"]
    res = client.post(f"/api/projects/{project_id}/try", json={"text": "x" * 6001})
    assert res.status_code == 422
    detail = res.json()["detail"]
    assert detail["code"] == "input_too_long"
    assert detail["message"] == "This input is 6001 characters. The limit is 6000."
