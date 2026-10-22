import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from system1.db import init_db
from system1.decisions.models import Decision, Feedback

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


def _decision(project_id: str, lane: str, probs: dict[str, float], **extra) -> Decision:
    top = max(probs, key=probs.get) if probs else None
    return Decision(
        org_id="org_a",
        project_id=project_id,
        source=extra.pop("source", "api"),
        lane=lane,
        model_reported=f"{lane}-fake",
        state_json="hello",
        answers_json={"decision": {"type": "choice", "choice": top, "probabilities": probs}} if probs else {},
        top_label=top,
        top_prob=probs.get(top) if top else None,
        latency_ms=1.0,
        policy_version=1,
        not_for_training=lane.startswith("jev"),
        **extra,
    )


def test_inbox_ranks_sys1_by_margin_and_never_jev(client_for):
    client = client_for("org_a")
    project_id, label = _setup(client)
    sure = _decision(project_id, "sys1", {"a": 0.9, "b": 0.1})
    unsure = _decision(project_id, "sys1", {"a": 0.5, "b": 0.45, "c": 0.05})
    middle = _decision(project_id, "sys1", {"a": 0.7, "b": 0.3})
    lone = _decision(project_id, "sys1", {})  # nothing stored: counts as sure
    jev_unsure = _decision(project_id, "jev", {"a": 0.51, "b": 0.49})  # a very close Jev call must not surface
    judged = _decision(project_id, "sys1", {"a": 0.5, "b": 0.5})
    scoring = _decision(project_id, "sys1", {"a": 0.5, "b": 0.5}, source="eval")
    flagged = _decision(project_id, "jev", {"a": 0.6, "b": 0.4}, needs_review=True)
    with Session(client.app.state.engine) as session:
        session.add_all([sure, unsure, middle, lone, jev_unsure, judged, scoring, flagged])
        session.commit()
        named = {"sure": sure, "unsure": unsure, "middle": middle, "lone": lone, "judged": judged}
        named |= {"flagged": flagged, "jev": jev_unsure}
        ids = {name: d.id for name, d in named.items()}
    client.post(f"/api/decisions/{ids['judged']}/feedback", json={"kind": "correction", "correct_label": label})

    items = client.get(f"/api/projects/{project_id}/inbox").json()["items"]

    assert [i["decision_id"] for i in items] == [ids["unsure"], ids["middle"], ids["sure"], ids["lone"], ids["flagged"]]
    assert [i["how_sure"] for i in items[:3]] == [pytest.approx(0.05), pytest.approx(0.4), pytest.approx(0.8)]
    assert items[3]["how_sure"] == 1.0 and items[4]["how_sure"] is None
    assert ids["jev"] not in {i["decision_id"] for i in items}
