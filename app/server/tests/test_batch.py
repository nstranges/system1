import csv
import io

import pytest
from sqlalchemy.orm import Session

from system1.adapters.fakes import FakeDecisionProvider, FakeLLM
from system1.adapters.modal_sys1 import ModalSys1Provider
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
    """Jobs write from their own sessions, so use a file database (see test_report.py)."""

    def build(org_id, **kwargs):
        kwargs.setdefault("engine", make_engine(f"sqlite:///{tmp_path / 'test.db'}"))
        return client_for(org_id, **kwargs)

    return build


@pytest.fixture(autouse=True)
def fast_polling(monkeypatch):
    monkeypatch.setattr(report_service, "POLL_INTERVAL_S", 0)


class AdapterTrainer:
    """Every run succeeds with a new adapter, which makes the first one live."""

    def start(self, dataset_ref: str, config: dict) -> TrainingJob:
        return TrainingJob(id="run-1", status="queued", message="Queued.")

    def status(self, job_id: str) -> TrainingJob:
        return TrainingJob(id=job_id, status="succeeded", message="Done.", adapter_ref="laya-outputs:projects/p/run-1")


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


class BatchRunner:
    """A deployed model with a batch call: sure about anything mentioning an invoice, unsure otherwise."""

    def __init__(self, fail: bool = False):
        self.batch_calls: list[int] = []
        self.fail = fail

    def _answer(self, state: str, questions: dict) -> dict:
        name = next(iter(questions))
        sure = "invoice" in state
        probs = {"billing": 0.95, "shipping": 0.05} if sure else {"shipping": 0.55, "billing": 0.45}
        return {"answers": {name: {"type": "choice", "choice": max(probs, key=probs.get), "probabilities": probs}}}

    async def decide(self, adapter_ref: str, state: str, questions: dict) -> dict:
        return self._answer(state, questions)

    async def decide_many(self, adapter_ref: str, states: list[str], questions: dict) -> list[dict]:
        self.batch_calls.append(len(states))
        if self.fail:
            raise RuntimeError("container crashed")
        return [self._answer(s, questions) for s in states]


def _client(client_for, runner, org="org_a", engine=None):
    llm = FakeLLM([])
    providers = Providers(
        jev=FakeDecisionProvider("jev", "jev-fake"),
        sys1=ModalSys1Provider(runner),
        llm=llm,
        trainer=AdapterTrainer(),
        generator=SimpleGenerator(llm),
    )
    return client_for(org, providers=providers, **({"engine": engine} if engine else {}))


def _upload(client, pid: str, text: str, name: str = "batch.csv"):
    return client.post(f"/api/projects/{pid}/batches", files={"file": (name, text.encode(), "text/csv")})


def _run(client, pid: str, text: str) -> dict:
    res = _upload(client, pid, text)
    assert res.status_code == 200, res.text
    wait_for_job(res.json()["job_id"])
    return client.get(f"/api/jobs/{res.json()['job_id']}").json()


def test_a_batch_fills_the_inbox_with_the_unsure_answers(client_for):
    runner = BatchRunner()
    client = _client(client_for, runner)
    pid = _project(client)
    _train(client, pid)

    job = _run(client, pid, "id,message\n1,my invoice is wrong\n2,where is my parcel\n3,box never came\n4,\n")
    assert job["status"] == "succeeded"
    result = job["result"]
    assert (result["answered"], result["unsure"], result["skipped"], result["failed"]) == (3, 2, 1, 0)
    assert result["top"][0] == {"key": "shipping", "count": 2}
    assert runner.batch_calls == [3]  # one call for the whole batch, not one per row

    inbox = client.get(f"/api/projects/{pid}/inbox").json()["items"]
    # The two unsure answers come first (they tie on how sure), ahead of the sure one.
    assert {i["state"] for i in inbox[:2]} == {"where is my parcel", "box never came"}
    assert inbox[2]["state"] == "my invoice is wrong"


def test_the_batch_downloads_with_its_answers(client_for):
    client = _client(client_for, BatchRunner())
    pid = _project(client)
    _train(client, pid)
    batch_id = _run(client, pid, "text\nmy invoice is wrong\nwhere is my parcel\n")["result"]["batch_id"]

    res = client.get(f"/api/projects/{pid}/batches/{batch_id}/download")
    assert res.status_code == 200 and res.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(res.text)))
    assert [(r["text"], r["answer"], r["runner_up"]) for r in rows] == [
        ("my invoice is wrong", "billing", "shipping"),
        ("where is my parcel", "shipping", "billing"),
    ]


def test_a_failed_model_call_counts_rows_as_unanswered(client_for):
    client = _client(client_for, BatchRunner(fail=True))
    pid = _project(client)
    _train(client, pid)
    job = _run(client, pid, "text\none\ntwo\n")
    assert job["result"]["failed"] == 2 and job["result"]["answered"] == 0
    assert "didn't answer 2 of 2" in job["message"]


def test_a_batch_needs_a_live_model(client_for):
    client = _client(client_for, BatchRunner())
    pid = _project(client)
    res = _upload(client, pid, "text\nhello\n")
    assert res.status_code == 422 and res.json()["detail"]["code"] == "batch_not_ready"


def test_an_empty_or_oversized_batch_is_refused(client_for, monkeypatch):
    from system1.batch import service as batch_service

    client = _client(client_for, BatchRunner())
    pid = _project(client)
    _train(client, pid)
    assert _upload(client, pid, "text\n\n").status_code == 422  # the upload parser refuses a file with no rows
    monkeypatch.setattr(batch_service, "BATCH_MAX_ROWS", 2)
    res = _upload(client, pid, "text\na\nb\nc\n")
    assert res.status_code == 422 and "at most 2 rows" in res.json()["detail"]["message"]


def test_another_org_cannot_download_a_batch(client_for):
    client = _client(client_for, BatchRunner())
    pid = _project(client)
    _train(client, pid)
    batch_id = _run(client, pid, "text\nmy invoice is wrong\n")["result"]["batch_id"]
    other = _client(client_for, BatchRunner(), org="org_b", engine=client.app.state.engine)
    assert other.get(f"/api/projects/{pid}/batches/{batch_id}/download").status_code == 404
