import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from system1.adapters.fakes import FakeDecisionProvider, FakeLLM
from system1.adapters.modal_sys1 import ModalSys1Provider
from system1.contracts.training import EvalAnswer, TrainingJob
from system1.datasets import service as dataset_service
from system1.datasets.service import NewExample
from system1.db import make_engine
from system1.decisions.models import Decision
from system1.generation.simple import SimpleGenerator
from system1.jobs.service import wait_for_job
from system1.projects.models import Project
from system1.providers import Providers
from system1.report import service as report_service

OPTIONS = [{"key": "billing", "name": "Billing"}, {"key": "shipping", "name": "Shipping"}]


@pytest.fixture
def client_for(client_for, tmp_path):
    """Training jobs write from their own sessions, so use a file database (see test_report.py)."""

    def build(org_id, **kwargs):
        kwargs.setdefault("engine", make_engine(f"sqlite:///{tmp_path / 'test.db'}"))
        return client_for(org_id, **kwargs)

    return build


@pytest.fixture(autouse=True)
def fast_polling(monkeypatch):
    monkeypatch.setattr(report_service, "POLL_INTERVAL_S", 0)


class ScriptedTrainer:
    """Each run scores your model on the test examples with the next accuracy in `accuracies`."""

    needs_examples = True

    def __init__(self, accuracies: list[float]):
        self.accuracies = list(accuracies)
        self.runs: list[dict] = []

    def start(self, dataset_ref: str, config: dict) -> TrainingJob:
        self.runs.append(config)
        return TrainingJob(id=f"run-{len(self.runs)}", status="queued", message="Queued.")

    def status(self, job_id: str) -> TrainingJob:
        config = self.runs[int(job_id.split("-")[1]) - 1]
        test = [e for e in config["examples"] if e["split"] == "test"]
        right = round(len(test) * self.accuracies[int(job_id.split("-")[1]) - 1])
        answers = [
            EvalAnswer(
                id=e["id"], pred=e["label"] if i < right else ("shipping" if e["label"] == "billing" else "billing")
            )
            for i, e in enumerate(test)
        ]
        return TrainingJob(
            id=job_id,
            status="succeeded",
            message="Done.",
            adapter_ref=f"laya-outputs:projects/p/{job_id}",
            evaluations={"sys1": answers},
        )


class UnsureRunner:
    """A deployed model that always picks billing, at 60%."""

    async def decide(self, adapter_ref: str, state: str, questions: dict) -> dict:
        name = next(iter(questions))
        return {
            "answers": {
                name: {"type": "choice", "choice": "billing", "probabilities": {"billing": 0.6, "shipping": 0.4}}
            }
        }


def _client(client_for, accuracies=(0.5, 1.0), org="org_a", engine=None):
    llm = FakeLLM([])
    providers = Providers(
        jev=FakeDecisionProvider("jev", "jev-fake"),
        sys1=ModalSys1Provider(UnsureRunner()),
        llm=llm,
        trainer=ScriptedTrainer(list(accuracies)),
        generator=SimpleGenerator(llm),
    )
    return client_for(org, providers=providers, **({"engine": engine} if engine else {}))


def _project(client) -> str:
    pid = client.post("/api/projects", json={"name": "Triage"}).json()["id"]
    policy = {"decision_question": "Where does it go?", "options": OPTIONS}
    assert client.put(f"/api/projects/{pid}/policy", json={"policy": policy}).status_code == 200
    with Session(client.app.state.engine) as session:
        rows = [NewExample(f"{o['key']} issue number {i}", o["key"], "generated") for o in OPTIONS for i in range(30)]
        dataset_service.add_examples(session, session.get(Project, pid), rows)
    return pid


def _train(client, pid: str) -> None:
    res = client.post(f"/api/projects/{pid}/training")
    assert res.status_code == 200, res.text
    wait_for_job(res.json()["job_id"])


def _try(client, pid: str, text: str) -> str:
    results = client.post(f"/api/projects/{pid}/try", json={"text": text}).json()["results"]
    return next(r for r in results if r["lane"] == "sys1")["decision_id"]


def test_inbox_offers_the_models_top_guesses(client_for):
    client = _client(client_for)
    pid = _project(client)
    _train(client, pid)
    _try(client, pid, "where is my parcel")
    item = client.get(f"/api/projects/{pid}/inbox").json()["items"][0]
    assert item["guesses"] == [{"key": "billing", "p": 0.6}, {"key": "shipping", "p": 0.4}]
    assert item["how_sure"] == pytest.approx(0.2)


def test_checked_answers_score_the_model_that_gave_them(client_for):
    client = _client(client_for)
    pid = _project(client)
    _train(client, pid)
    live = client.get(f"/api/projects/{pid}").json()["live_model_id"]

    right, wrong = _try(client, pid, "my invoice is off"), _try(client, pid, "where is my parcel")
    with Session(client.app.state.engine) as session:
        assert session.get(Decision, right).sys1_model_id == live
    client.post(f"/api/decisions/{right}/feedback", json={"kind": "confirm"})
    client.post(f"/api/decisions/{wrong}/feedback", json={"kind": "correction", "correct_label": "shipping"})

    summary = client.get(f"/api/projects/{pid}/improve").json()
    # A confirmed answer from your model is a checked label too, so both are ready to learn from.
    assert summary == {"waiting": 0, "ready": 2, "live_checked": 2, "live_right": 1}
    model = client.get("/api/models").json()[0]
    assert (model["checked"], model["checked_right"]) == (2, 1)


def test_a_better_retrain_is_recommended_but_not_made_live(client_for):
    client = _client(client_for, accuracies=(0.5, 1.0))
    pid = _project(client)
    _train(client, pid)
    wrong = _try(client, pid, "where is my parcel")
    client.post(f"/api/decisions/{wrong}/feedback", json={"kind": "correction", "correct_label": "shipping"})
    _train(client, pid)

    newest, live = client.get("/api/models", params={"project_id": pid}).json()
    assert newest["corrections_used"] == 1 and not newest["live"] and live["live"]
    comparison = client.get(f"/api/models/{newest['id']}/compare").json()
    assert comparison["recommend"] and comparison["same_test_set"]
    assert comparison["diff"] == pytest.approx(0.5)
    assert [c["key"] for c in comparison["improved"]] and comparison["worsened"] == []
    assert client.get(f"/api/projects/{pid}").json()["live_model_id"] == live["id"]  # waits for someone to pick it


def test_a_worse_retrain_says_to_keep_the_live_model(client_for):
    client = _client(client_for, accuracies=(1.0, 0.5))
    pid = _project(client)
    _train(client, pid)
    _train(client, pid)
    newest = client.get("/api/models", params={"project_id": pid}).json()[0]
    comparison = client.get(f"/api/models/{newest['id']}/compare").json()
    assert not comparison["recommend"] and "keep the live one" in comparison["sentence"]
    assert comparison["worsened"]


def test_comparing_the_live_model_with_itself_recommends_nothing(client_for):
    client = _client(client_for)
    pid = _project(client)
    _train(client, pid)
    live = client.get(f"/api/projects/{pid}").json()["live_model_id"]
    comparison = client.get(f"/api/models/{live}/compare").json()
    assert not comparison["recommend"] and comparison["sentence"] == "This is the live model."


def test_another_org_cannot_compare_or_read_the_summary(client_for):
    client = _client(client_for)
    pid = _project(client)
    _train(client, pid)
    live = client.get(f"/api/projects/{pid}").json()["live_model_id"]
    other = _client(client_for, org="org_b", engine=client.app.state.engine)
    assert other.get(f"/api/models/{live}/compare").status_code == 404
    assert other.get(f"/api/projects/{pid}/improve").status_code == 404


def test_eval_answers_never_count_as_checked(client_for):
    client = _client(client_for)
    pid = _project(client)
    _train(client, pid)
    with Session(client.app.state.engine) as session:
        assert session.scalars(select(Decision).where(Decision.source == "eval", Decision.lane == "sys1")).all() == []
    assert client.get("/api/models").json()[0]["checked"] == 0
