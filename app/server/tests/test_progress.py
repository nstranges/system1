import pytest
from sqlalchemy.orm import Session

from system1.adapters.fakes import FakeDecisionProvider, FakeLLM, PreviewTrainer
from system1.auth.principal import Principal
from system1.datasets import service as dataset_service
from system1.datasets.service import NewExample
from system1.db import make_engine
from system1.domain.policy import Option, Policy
from system1.generation.simple import SimpleGenerator
from system1.jobs.service import wait_for_job
from system1.projects import service as project_service
from system1.providers import Providers
from system1.report import service as report_service

PRINCIPAL = Principal(user_id="user_1", org_id="org_a", org_role="admin", org_slug="org_a")
OPTIONS = [{"key": k, "name": k.upper()} for k in "abc"]
FLAGSHIP = "tallyfern-triage"


@pytest.fixture
def client_for(client_for, tmp_path):
    """Training jobs write from their own sessions, so they need a file database rather than the shared in-memory one."""

    def build(org_id, **kwargs):
        kwargs.setdefault("engine", make_engine(f"sqlite:///{tmp_path / 'test.db'}"))
        return client_for(org_id, **kwargs)

    return build


@pytest.fixture(autouse=True)
def fast_polling(monkeypatch):
    monkeypatch.setattr(report_service, "POLL_INTERVAL_S", 0)


def _project(client, options=OPTIONS) -> str:
    pid = client.post("/api/projects", json={"name": "Triage"}).json()["id"]
    policy = {"decision_question": "Where does it go?", "options": options}
    assert client.put(f"/api/projects/{pid}/policy", json={"policy": policy}).status_code == 200
    return pid


def _rows(label: str, n: int, source: str = "uploaded", how_sure: float | None = None, prefix: str = "") -> list:
    return [NewExample(f"{prefix}{label} message {i}", label, source, how_sure) for i in range(n)]


def _add(client, pid: str, rows: list) -> None:
    with Session(client.app.state.engine) as session:
        project = project_service.get_project(session, PRINCIPAL, pid)
        dataset_service.add_examples(session, project, rows)


def _progress(client, pid):
    res = client.get(f"/api/projects/{pid}/progress")
    assert res.status_code == 200, res.text
    return res.json()


def _stages(p):
    return {s["id"]: (s["status"], s["note"]) for s in p["stages"]}


def test_blank_project_progress(client_for):
    client = client_for("org_a")
    pid = client.post("/api/projects", json={"name": "Blank"}).json()["id"]
    p = _progress(client, pid)
    assert [s["id"] for s in p["stages"]] == ["define", "data", "review", "train", "use", "improve"]
    s = _stages(p)
    assert s["define"] == ("ready", "Add at least two buckets")
    assert s["data"] == ("blocked", "Define your buckets first")
    assert s["review"] == ("blocked", "Add examples first")
    assert s["train"] == ("blocked", "Needs 30 examples per bucket")
    assert s["use"] == ("blocked", "Define your buckets first")
    assert s["improve"] == ("blocked", "Needs a live model")
    assert p["next"] == "define" and p["examples"] == 0 and p["accuracy"] is None and p["jev_accuracy"] is None


def test_buckets_with_problems_are_not_done(client_for):
    # Saving refuses an invalid policy, so only an older saved version can carry problems.
    client = client_for("org_a")
    pid = client.post("/api/projects", json={"name": "Old"}).json()["id"]
    policy = Policy(
        decision_question="Where?", options=[Option(key="Not Snake", name="Bad"), Option(key="b", name="B")]
    )
    with Session(client.app.state.engine) as session:
        project_service._add_version(session, pid, 2, policy, "user_1")
        session.commit()
    assert _stages(_progress(client, pid))["define"] == ("ready", "Fix the problems in your buckets")


def test_enough_uploaded_examples_points_at_train(client_for):
    client = client_for("org_a")
    pid = _project(client)
    _add(client, pid, _rows("a", 30) + _rows("b", 30) + _rows("c", 30))
    p = _progress(client, pid)
    s = _stages(p)
    assert s["define"] == ("done", "3 buckets")
    assert s["data"] == ("done", "90 examples")
    assert s["review"] == ("done", "Nothing left to check")
    assert s["train"] == ("ready", "Ready to train")
    assert s["use"] == ("ready", "Try it, then get a key")
    assert p["next"] == "train" and p["examples"] == 90


def test_short_bucket_blocks_training(client_for):
    client = client_for("org_a")
    pid = _project(client)
    _add(client, pid, _rows("a", 30) + _rows("b", 30) + _rows("c", 29))
    s = _stages(_progress(client, pid))
    assert s["data"] == ("ready", "1 bucket needs more examples")
    assert s["train"] == ("blocked", "Needs 30 examples per bucket")


def test_several_short_buckets_are_counted(client_for):
    client = client_for("org_a")
    pid = _project(client)
    _add(client, pid, _rows("a", 30) + _rows("b", 3))
    assert _stages(_progress(client, pid))["data"] == ("ready", "2 buckets need more examples")


def test_generated_examples_wait_in_review(client_for):
    client = client_for("org_a")
    pid = _project(client)
    _add(client, pid, _rows("a", 25) + _rows("a", 5, "generated", 0.4, "gen ") + _rows("b", 30) + _rows("c", 30))
    s = _stages(_progress(client, pid))
    assert s["review"] == ("ready", "5 to check")


def test_review_queue_at_its_cap_reads_as_more(client_for):
    client = client_for("org_a")
    pid = _project(client)
    _add(client, pid, _rows("a", 40, "generated", 0.4) + _rows("b", 30) + _rows("c", 30))
    assert _stages(_progress(client, pid))["review"] == ("ready", "30+ to check")


def test_preview_training_is_not_a_model(client_for):
    llm = FakeLLM([])
    providers = Providers(
        jev=FakeDecisionProvider("jev", "jev-fake"),
        sys1=None,
        llm=llm,
        trainer=PreviewTrainer(duration_s=0),
        generator=SimpleGenerator(llm),
    )
    client = client_for("org_a", providers=providers)
    pid = _project(client, OPTIONS[:2])
    _add(client, pid, _rows("a", 30, "generated") + _rows("b", 30, "generated"))
    job_id = client.post(f"/api/projects/{pid}/training").json()["job_id"]
    wait_for_job(job_id)
    p = _progress(client, pid)
    assert _stages(p)["train"] == ("done", "Preview run, no model yet")
    assert p["accuracy"] is None
    # Jev's row is a real score, so it still shows.
    assert p["jev_accuracy"] is not None


def test_flagship_progress(client_for):
    client = client_for("org_a")
    pid = client.post("/api/projects", json={"name": "T", "template_id": FLAGSHIP}).json()["id"]
    p = _progress(client, pid)
    s = _stages(p)
    assert s["review"] == ("done", "Labelled by exact rules")
    assert s["train"][0] == "done" and s["train"][1].startswith("Your model: ")
    assert p["accuracy"] is not None and p["jev_accuracy"] is not None


def test_key_marks_use_done(client_for):
    client = client_for("org_a")
    pid = _project(client)
    assert client.post(f"/api/projects/{pid}/keys").status_code == 200
    assert _stages(_progress(client, pid))["use"] == ("done", "Connected")


def test_other_org_gets_404(client_for):
    pid = client_for("org_a").post("/api/projects", json={"name": "A"}).json()["id"]
    assert client_for("org_b").get(f"/api/projects/{pid}/progress").status_code == 404
