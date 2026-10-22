from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from system1.auth.principal import Principal
from system1.datasets import service
from system1.datasets.constants import MIN_PER_BUCKET, MIN_TEST_PER_BUCKET
from system1.datasets.models import Example
from system1.datasets.service import NewExample
from system1.db import _add_missing_columns
from system1.projects import service as project_service
from system1.projects.models import Project

PRINCIPAL = Principal(user_id="user_1", org_id="org_a", org_role="admin", org_slug="org_a")
OPTIONS = [{"key": k, "name": k.upper()} for k in "abc"]


def _project(client, options=OPTIONS) -> str:
    pid = client.post("/api/projects", json={"name": "Triage"}).json()["id"]
    policy = {"decision_question": "Where does it go?", "options": options}
    assert client.put(f"/api/projects/{pid}/policy", json={"policy": policy}).status_code == 200
    return pid


def _rows(label: str, n: int, source: str = "uploaded", how_sure: float | None = None, prefix: str = "") -> list:
    return [NewExample(f"{prefix}{label} message {i}", label, source, how_sure) for i in range(n)]


def _add(client, pid: str, rows: list) -> int:
    with Session(client.app.state.engine) as session:
        project = project_service.get_project(session, PRINCIPAL, pid)
        return service.add_examples(session, project, rows)


def _freeze(client, pid: str) -> None:
    with Session(client.app.state.engine) as session:
        service.freeze(session, project_service.get_project(session, PRINCIPAL, pid))


def _all(client, pid: str) -> list[Example]:
    with Session(client.app.state.engine) as session:
        rows = list(session.query(Example).filter_by(project_id=pid).order_by(Example.id))
        session.expunge_all()
        return rows


def _health(client, pid: str) -> dict:
    return client.get(f"/api/projects/{pid}/examples/health").json()


def test_split_fills_test_quota_then_train_cal(client_for):
    client = client_for("org_a")
    pid = _project(client)
    assert _add(client, pid, _rows("a", 30) + _rows("b", 12) + _rows("c", 5)) == 47

    health = _health(client, pid)
    # 30 rows: quota max(6, round(6.0)) = 6, then 24 split 21 train / 3 cal.
    assert health["per_bucket"]["a"] == {"train": 21, "cal": 3, "test": 6, "total": 30}
    # 12 rows: the minimum quota of 6 beats 20%.
    assert health["per_bucket"]["b"] == {"train": 5, "cal": 1, "test": 6, "total": 12}
    # 5 rows can't fill a quota and still train, so everything trains until the bucket grows.
    assert health["per_bucket"]["c"] == {"train": 5, "cal": 0, "test": 0, "total": 5}
    assert health["below_minimum"] == ["b", "c"] and MIN_PER_BUCKET == 30
    assert health["sources"] == {"uploaded": 47, "generated": 0, "corrected": 0}
    assert health["frozen"] is False and health["dataset_version"] == 1 and health["test_set_version"] == 1

    # Growing a bucket re-runs the split deterministically while nothing is frozen.
    assert _add(client, pid, _rows("c", 20, prefix="more ")) == 20
    assert _health(client, pid)["per_bucket"]["c"] == {"train": 17, "cal": 2, "test": 6, "total": 25}


def test_duplicates_skipped(client_for):
    client = client_for("org_a")
    pid = _project(client)
    first = [NewExample("Where is  my refund?", "a", "uploaded"), NewExample("where is my REFUND?", "b", "uploaded")]
    assert _add(client, pid, first + [NewExample({"x": 1, "y": 2}, "a", "uploaded")]) == 2
    assert (
        _add(
            client,
            pid,
            [NewExample("WHERE IS MY\nrefund?", "c", "generated"), NewExample({"y": 2, "x": 1}, "a", "generated")],
        )
        == 0
    )
    assert _health(client, pid)["dataset_version"] == 1
    assert sum(b["total"] for b in _health(client, pid)["per_bucket"].values()) == 2


def test_after_freeze_test_rows_never_change(client_for):
    client = client_for("org_a")
    pid = _project(client)
    _add(client, pid, _rows("a", 30) + _rows("b", 30))
    _freeze(client, pid)
    _freeze(client, pid)  # idempotent
    before = {(r.id, r.label, r.split) for r in _all(client, pid) if r.split == "test"}
    assert len(before) == 12

    _add(client, pid, _rows("a", 20, prefix="late ") + _rows("b", 20, prefix="late "))
    renamed = [{"key": "a", "name": "Renamed A"}, *OPTIONS[1:]]
    policy = {"decision_question": "Where does it go?", "options": renamed}
    assert client.put(f"/api/projects/{pid}/policy", json={"policy": policy}).status_code == 200
    train_id = next(r.id for r in _all(client, pid) if r.split == "train" and r.label == "a")
    with Session(client.app.state.engine) as session:
        project = project_service.get_project(session, PRINCIPAL, pid)
        service.review(session, project, train_id, "move", "b")

    rows = _all(client, pid)
    assert {(r.id, r.label, r.split) for r in rows if r.split == "test"} == before
    assert next(r for r in rows if r.id == train_id).label == "b"
    health = _health(client, pid)
    assert health["test_set_version"] == 1 and health["frozen"] is True and health["dataset_version"] >= 3
    assert health["per_bucket"]["a"]["test"] == 6


def test_new_bucket_after_freeze_fills_test_and_bumps_version(client_for):
    client = client_for("org_a")
    pid = _project(client)
    _add(client, pid, _rows("a", 30))
    _freeze(client, pid)
    policy = {"decision_question": "Where does it go?", "options": [*OPTIONS, {"key": "d", "name": "D"}]}
    assert client.put(f"/api/projects/{pid}/policy", json={"policy": policy}).status_code == 200

    assert _add(client, pid, _rows("d", 10, "generated", 0.5)) == 10
    health = _health(client, pid)
    assert health["per_bucket"]["d"]["test"] == MIN_TEST_PER_BUCKET
    assert health["per_bucket"]["d"]["total"] == 10
    assert health["test_set_version"] == 2

    # The quota is met, so later rows go to train or calibration and the version holds.
    _add(client, pid, _rows("d", 10, prefix="more "))
    health = _health(client, pid)
    assert health["per_bucket"]["d"]["test"] == MIN_TEST_PER_BUCKET and health["test_set_version"] == 2


def test_delete_bucket_with_frozen_test_requires_reset(client_for):
    client = client_for("org_a")
    pid = _project(client)
    _add(client, pid, _rows("a", 30) + _rows("c", 30))
    _freeze(client, pid)
    url = f"/api/projects/{pid}/buckets/c/delete"

    refused = client.post(url, json={"mode": "drop"})
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "test_reset_required"
    assert client.post(url, json={"mode": "move"}).status_code == 422
    assert client.post(url, json={"mode": "move", "to": "c"}).status_code == 422
    assert client.post(url, json={"mode": "move", "to": "zzz"}).status_code == 422
    assert _health(client, pid)["per_bucket"]["c"]["total"] == 30

    done = client.post(url, json={"mode": "move", "to": "a", "reset_test": True})
    assert done.status_code == 200
    health = _health(client, pid)
    assert "c" not in health["per_bucket"] and health["per_bucket"]["a"]["total"] == 60
    assert health["test_set_version"] == 2
    policy = client.get(f"/api/projects/{pid}/policy").json()["policy"]
    assert [o["key"] for o in policy["options"]] == ["a", "b"]

    # The policy must keep at least two buckets, so this is refused before touching any example.
    _add(client, pid, _rows("b", 3))
    drop = client.post(f"/api/projects/{pid}/buckets/b/delete", json={"mode": "drop", "reset_test": True})
    assert drop.status_code == 422  # a policy needs at least two buckets


def test_review_queue_least_sure_first_excludes_frozen_test(client_for):
    client = client_for("org_a")
    pid = _project(client)
    rows = [NewExample(f"a {i}", "a", "generated", 0.05 * (i + 1)) for i in range(40)]
    _add(client, pid, rows + [NewExample("no score", "a", "generated"), NewExample("up", "a", "uploaded", 0.01)])

    before = client.get(f"/api/projects/{pid}/review").json()
    assert [r["how_sure"] for r in before] == sorted(r["how_sure"] for r in before)
    assert before[0]["how_sure"] == 0.05 and len(before) == 30
    assert {r["split"] for r in before} >= {"test"}

    _freeze(client, pid)
    after = client.get(f"/api/projects/{pid}/review").json()
    assert after and all(r["split"] != "test" for r in after)
    assert [r["how_sure"] for r in after] == sorted(r["how_sure"] for r in after)
    assert all(r["source"] == "generated" and r["how_sure"] is not None for r in after)

    first = after[0]["id"]
    assert client.post(f"/api/examples/{first}/review", json={"action": "agree"}).json()["review"] == "agree"
    assert first not in {r["id"] for r in client.get(f"/api/projects/{pid}/review").json()}

    test_id = next(r.id for r in _all(client, pid) if r.split == "test")
    locked = client.post(f"/api/examples/{test_id}/review", json={"action": "agree"})
    assert locked.status_code == 409 and locked.json()["detail"]["code"] == "test_set_frozen"
    bad = client.post(f"/api/examples/{after[1]['id']}/review", json={"action": "move", "to": "zzz"})
    assert bad.status_code == 422


def test_other_org_404_examples_and_review(client_for):
    owner = client_for("org_a")
    pid = _project(owner)
    _add(owner, pid, _rows("a", 8, "generated", 0.3))
    example_id = _all(owner, pid)[0].id
    other = client_for("org_b", engine=owner.app.state.engine)

    for method, path, kwargs in [
        ("get", f"/api/projects/{pid}/examples", {}),
        ("get", f"/api/projects/{pid}/examples/health", {}),
        ("get", f"/api/projects/{pid}/review", {}),
        ("post", f"/api/examples/{example_id}/review", {"json": {"action": "agree"}}),
        ("post", f"/api/projects/{pid}/buckets/a/delete", {"json": {"mode": "drop"}}),
    ]:
        assert getattr(other, method)(path, **kwargs).status_code == 404, path
    listed = owner.get(f"/api/projects/{pid}/examples?source=generated&limit=5").json()
    assert len(listed) == 5 and set(listed[0]) == {"id", "input", "label", "source", "split", "how_sure", "review"}
    assert owner.get(f"/api/projects/{pid}/examples?limit=500").status_code == 422
    assert _all(owner, pid)[0].review is None


def test_removing_or_renaming_a_bucket_key_with_examples_is_refused(client_for):
    client = client_for("org_a")
    pid = _project(client)
    _add(client, pid, _rows("c", 3))
    for options in ([OPTIONS[0], OPTIONS[1]], [OPTIONS[0], OPTIONS[1], {"key": "c2", "name": "C"}]):
        res = client.put(f"/api/projects/{pid}/policy", json={"policy": {"decision_question": "Q", "options": options}})
        assert res.status_code == 409 and res.json()["detail"]["code"] == "bucket_has_examples"
        assert "Delete bucket" in res.json()["detail"]["message"]
    # A bucket without examples can still go, and a new key can be added.
    options = [OPTIONS[0], OPTIONS[2], {"key": "z", "name": "Z"}]
    assert (
        client.put(
            f"/api/projects/{pid}/policy", json={"policy": {"decision_question": "Q", "options": options}}
        ).status_code
        == 200
    )


def test_new_project_columns_are_added_to_an_old_projects_table():
    engine = create_engine("sqlite://")
    cols = [c for c in Project.__table__.columns if c.name not in {"frozen_at", "test_set_version", "dataset_version"}]
    old = ", ".join(f"{c.name} {c.type.compile(engine.dialect)}" for c in cols)
    with engine.begin() as conn:
        conn.execute(text(f"CREATE TABLE projects ({old})"))
        conn.execute(
            text(
                "INSERT INTO projects (id, org_id, name, stage, default_lane, created_by, created_at) VALUES ('p', 'o', 'n', 'usecase', 'jev', 'u', '2026-10-22')"
            )
        )
    _add_missing_columns(engine, "projects")
    assert {"frozen_at", "test_set_version", "dataset_version"} <= {
        c["name"] for c in inspect(engine).get_columns("projects")
    }
    with Session(engine) as session:
        project = session.get(Project, "p")
        assert (project.frozen_at, project.test_set_version, project.dataset_version) == (None, 1, 0)
