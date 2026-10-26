import asyncio

import pytest
from sqlalchemy.orm import Session

from system1.adapters.fakes import FakeDecisionProvider, FakeLLM, PreviewTrainer
from system1.adapters.modal_sys1 import ModalSys1Provider
from system1.contracts.decisions import DecisionRequest, ProviderError
from system1.contracts.training import TrainingJob
from system1.datasets import service as dataset_service
from system1.datasets.service import NewExample
from system1.db import make_engine
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


class AdapterTrainer:
    """Every run succeeds with a new adapter."""

    def __init__(self):
        self.runs = 0

    def start(self, dataset_ref: str, config: dict) -> TrainingJob:
        self.runs += 1
        return TrainingJob(id=f"run-{self.runs}", status="queued", message="Queued.")

    def status(self, job_id: str) -> TrainingJob:
        return TrainingJob(
            id=job_id, status="succeeded", message="Done.", adapter_ref=f"laya-outputs:projects/p/{job_id}"
        )


class RecordingRunner:
    """Stands in for the deployed Decider: answers the first option and records which adapter it was asked for."""

    def __init__(self, fail: bool = False):
        self.adapters: list[str] = []
        self.fail = fail

    async def decide(self, adapter_ref: str, state: str, questions: dict) -> dict:
        self.adapters.append(adapter_ref)
        if self.fail:
            raise RuntimeError("CUDA out of memory")
        name, question = next(iter(questions.items()))
        first, second = list(question["criteria"])[:2]
        return {"answers": {name: {"type": "choice", "choice": first, "probabilities": {first: 0.95, second: 0.05}}}}


def _providers(trainer=None, sys1=None) -> Providers:
    llm = FakeLLM([])
    return Providers(
        jev=FakeDecisionProvider("jev", "jev-fake"),
        sys1=sys1,
        llm=llm,
        trainer=trainer or AdapterTrainer(),
        generator=SimpleGenerator(llm),
    )


def _project(client, name: str = "Triage") -> str:
    pid = client.post("/api/projects", json={"name": name}).json()["id"]
    policy = {"decision_question": "Where does it go?", "options": OPTIONS}
    assert client.put(f"/api/projects/{pid}/policy", json={"policy": policy}).status_code == 200
    with Session(client.app.state.engine) as session:
        project = session.get(Project, pid)
        rows = [NewExample(f"{o['key']} issue number {i}", o["key"], "generated") for o in OPTIONS for i in range(30)]
        dataset_service.add_examples(session, project, rows)
    return pid


def _train(client, pid: str) -> dict:
    res = client.post(f"/api/projects/{pid}/training")
    assert res.status_code == 200, res.text
    wait_for_job(res.json()["job_id"])
    return client.get(f"/api/jobs/{res.json()['job_id']}").json()


def _key(client, pid: str) -> dict:
    return {"Authorization": f"Bearer {client.post(f'/api/projects/{pid}/keys').json()['key']}"}


def test_first_model_goes_live_and_a_retrain_waits_to_be_picked(client_for):
    client = client_for("org_a", providers=_providers())
    pid = _project(client)
    _train(client, pid)
    first = client.get("/api/models").json()
    assert len(first) == 1 and first[0]["live"] and first[0]["project_name"] == "Triage"
    assert first[0]["jev_accuracy"] is not None
    assert client.get(f"/api/projects/{pid}").json()["live_model_id"] == first[0]["id"]

    _train(client, pid)
    models = client.get("/api/models", params={"project_id": pid}).json()
    assert [m["live"] for m in models] == [False, True]  # newest first; retraining didn't move the live one

    res = client.post(f"/api/models/{models[0]['id']}/live")
    assert res.status_code == 200 and res.json()["live_model_id"] == models[0]["id"]
    assert [m["live"] for m in client.get("/api/models").json()] == [True, False]


def test_models_survive_a_new_session_and_list_across_projects(client_for):
    client = client_for("org_a", providers=_providers())
    for name in ("Triage", "Refunds"):
        _train(client, _project(client, name))
    # A fresh client on the same database is a person signing back in.
    again = client_for("org_a", providers=_providers(), engine=client.app.state.engine)
    assert {m["project_name"] for m in again.get("/api/models").json()} == {"Triage", "Refunds"}


def test_preview_runs_are_not_models(client_for):
    client = client_for("org_a", providers=_providers(trainer=PreviewTrainer(duration_s=0)))
    pid = _project(client)
    _train(client, pid)
    assert client.get("/api/models").json() == []
    assert client.get(f"/api/projects/{pid}").json()["live_model_id"] is None


def test_another_org_cannot_see_or_pick_your_models(client_for):
    client = client_for("org_a", providers=_providers())
    pid = _project(client)
    _train(client, pid)
    model_id = client.get("/api/models").json()[0]["id"]

    other = client_for("org_b", providers=_providers(), engine=client.app.state.engine)
    assert other.get("/api/models").json() == []
    assert other.get("/api/models", params={"project_id": pid}).status_code == 404
    assert other.post(f"/api/models/{model_id}/live").status_code == 404


def test_endpoint_answers_with_the_projects_live_model(client_for):
    runner = RecordingRunner()
    client = client_for("org_a", providers=_providers(sys1=ModalSys1Provider(runner)))
    pid = _project(client)
    headers = _key(client, pid)

    # Before any training there is nothing to answer with, and auto quietly uses Jev.
    assert client.post("/v1/systemone", json={"state": "hi", "model": "sys1"}, headers=headers).status_code == 502
    assert client.post("/v1/systemone", json={"state": "hi", "model": "auto"}, headers=headers).json()["model"] == (
        "jev-fake"
    )
    assert client.get("/api/config").json() == {"sys1_available": True, "sys1_needs_live_model": True}

    _train(client, pid)
    _train(client, pid)
    res = client.post("/v1/systemone", json={"state": "my parcel is late", "model": "sys1"}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["model"] == "sys1" and res.json()["answers"]["decision"]["choice"] == "billing"
    assert runner.adapters == ["laya-outputs:projects/p/run-1"]

    newest = client.get("/api/models").json()[0]["id"]
    client.post(f"/api/models/{newest}/live")
    client.post("/v1/systemone", json={"state": "again", "model": "sys1"}, headers=headers)
    assert runner.adapters[-1] == "laya-outputs:projects/p/run-2"


def test_try_leaves_your_model_out_until_one_is_live(client_for):
    client = client_for("org_a", providers=_providers(sys1=ModalSys1Provider(RecordingRunner())))
    pid = _project(client)
    lanes = [r["lane"] for r in client.post(f"/api/projects/{pid}/try", json={"text": "hi"}).json()["results"]]
    assert "sys1" not in lanes
    _train(client, pid)
    lanes = [r["lane"] for r in client.post(f"/api/projects/{pid}/try", json={"text": "hi"}).json()["results"]]
    assert "sys1" in lanes


def test_modal_provider_turns_remote_failures_into_a_retryable_error():
    provider = ModalSys1Provider(RecordingRunner(fail=True))
    request = DecisionRequest(model="laya-outputs:projects/p/run-1", state={"text": "hi"}, questions={})
    with pytest.raises(ProviderError) as caught:
        asyncio.run(provider.decide(request))
    assert caught.value.retryable


def test_modal_provider_gives_up_on_a_cold_start_that_never_finishes():
    class Hanging:
        async def decide(self, adapter_ref, state, questions):
            await asyncio.sleep(10)

    provider = ModalSys1Provider(Hanging(), timeout_s=0.01)
    with pytest.raises(ProviderError):
        asyncio.run(provider.decide(DecisionRequest(model="m", state="hi", questions={})))
