from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from system1.db import init_db
from system1.decisions.models import Feedback

FLAGSHIP = "tallyfern-triage"


def _setup(client):
    project_id = client.post("/api/projects", json={"name": "P", "template_id": FLAGSHIP}).json()["id"]
    options = client.get(f"/api/projects/{project_id}/policy").json()["policy"]["options"]
    return project_id, options[0]["key"]


def _lanes(client, project_id: str, **body) -> dict[str, str]:
    results = client.post(f"/api/projects/{project_id}/try", json=body).json()["results"]
    return {r["lane"]: r["decision_id"] for r in results}


def _pool(client, project_id: str) -> int:
    return client.get(f"/api/projects/{project_id}/training-pool").json()["count"]


def test_feedback_on_test_item_is_never_training_eligible(client_for):
    client = client_for("org_a")
    project_id, label = _setup(client)
    sample = client.get(f"/api/projects/{project_id}/samples").json()[0]["id"]
    decision_id = _lanes(client, project_id, sample_id=sample)["sys1"]

    res = client.post(f"/api/decisions/{decision_id}/feedback", json={"kind": "correction", "correct_label": label})
    assert res.status_code == 200
    with Session(client.app.state.engine) as session:
        row = session.query(Feedback).one()
        assert row.is_test_item and not row.training_eligible
    assert _pool(client, project_id) == 0


def test_confirming_a_jev_answer_is_not_training_eligible(client_for):
    client = client_for("org_a")
    project_id, label = _setup(client)
    lanes = _lanes(client, project_id, text="my invoice is wrong")

    client.post(f"/api/decisions/{lanes['jev']}/feedback", json={"kind": "confirm"})
    assert _pool(client, project_id) == 0
    # A person's correction is theirs, so it counts even when Jev was the one who got it wrong.
    client.post(f"/api/decisions/{lanes['jev']}/feedback", json={"kind": "correction", "correct_label": label})
    assert _pool(client, project_id) == 1
    client.post(f"/api/decisions/{lanes['sys1']}/feedback", json={"kind": "confirm"})
    assert _pool(client, project_id) == 2

    bad = client.post(f"/api/decisions/{lanes['sys1']}/feedback", json={"kind": "correction", "correct_label": "nope"})
    assert bad.status_code == 422


def test_other_org_cannot_post_feedback(client_for):
    owner = client_for("org_a")
    project_id, label = _setup(owner)
    decision_id = _lanes(owner, project_id, text="hello")["sys1"]
    other = client_for("org_b", engine=owner.app.state.engine)

    res = other.post(f"/api/decisions/{decision_id}/feedback", json={"kind": "correction", "correct_label": label})
    assert res.status_code == 404
    with Session(owner.app.state.engine) as session:
        assert session.query(Feedback).count() == 0


def test_init_db_adds_missing_feedback_columns(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE feedback (id VARCHAR PRIMARY KEY, org_id VARCHAR, project_id VARCHAR, "
                "decision_id VARCHAR, correct_json JSON, created_at DATETIME)"
            )
        )
    init_db(engine)
    columns = {c["name"] for c in inspect(engine).get_columns("feedback")}
    assert {"kind", "user_id", "correct_label", "is_test_item", "training_eligible"} <= columns


def test_latest_verdict_replaces_the_earlier_one(client_for):
    client = client_for("org_a")
    project_id, label = _setup(client)
    decision_id = _lanes(client, project_id, text="refund please")["sys1"]
    url = f"/api/decisions/{decision_id}/feedback"

    client.post(url, json={"kind": "confirm"})
    client.post(url, json={"kind": "correction", "correct_label": label})
    other = client.get(f"/api/projects/{project_id}/policy").json()["policy"]["options"][1]["key"]
    client.post(url, json={"kind": "correction", "correct_label": other})
    with Session(client.app.state.engine) as session:
        row = session.query(Feedback).one()
        assert row.kind == "correction" and row.correct_label == other and row.training_eligible
    assert _pool(client, project_id) == 1
