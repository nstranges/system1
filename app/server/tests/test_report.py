import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from system1.adapters.fakes import FakeDecisionProvider, FakeLLM, PreviewTrainer
from system1.contracts.decisions import DecisionRequest, ProviderError
from system1.contracts.training import TrainingJob
from system1.datasets import service as dataset_service
from system1.datasets.models import Example
from system1.datasets.service import NewExample
from system1.db import make_engine
from system1.decisions.models import Decision, Feedback
from system1.generation.simple import SimpleGenerator
from system1.jobs.models import Job
from system1.jobs.service import wait_for_job
from system1.projects.models import Project
from system1.providers import Providers
from system1.report import service as report_service
from system1.report.models import JevEval, ReportCard
from system1.report.stats import accuracy_ci, paired_diff_ci, per_bucket_accuracy, top_confusions
from system1.usage import TokenUsage

OPTIONS = [{"key": "billing", "name": "Billing"}, {"key": "shipping", "name": "Shipping"}]
FLAGSHIP = "tallyfern-triage"


@pytest.fixture
def client_for(client_for, tmp_path):
    """Training jobs write from their own sessions while a request is still closing its. The in-memory test
    database has a single shared connection, so those would trip over each other: use a file database."""

    def build(org_id, **kwargs):
        kwargs.setdefault("engine", make_engine(f"sqlite:///{tmp_path / 'test.db'}"))
        return client_for(org_id, **kwargs)

    return build


@pytest.fixture(autouse=True)
def fast_polling(monkeypatch):
    monkeypatch.setattr(report_service, "POLL_INTERVAL_S", 0)


class CountingJev(FakeDecisionProvider):
    def __init__(self):
        super().__init__("jev", "jev-fake")
        self.calls = 0

    async def decide(self, req: DecisionRequest):
        self.calls += 1
        return await super().decide(req)


class FirstOptionProvider:
    """Always answers the first bucket, so it is right on exactly half of a balanced test set."""

    name = "sys1"

    async def decide(self, req: DecisionRequest):
        return await FakeDecisionProvider("sys1", "sys1-fake").decide(req.model_copy(update={"state": ""}))


class FinishingTrainer:
    def __init__(self, status: str, message: str = "Done.", adapter_ref: str | None = None):
        self._status, self._message, self._adapter_ref = status, message, adapter_ref

    def start(self, dataset_ref: str, config: dict) -> TrainingJob:
        self.started_with = (dataset_ref, config)
        return TrainingJob(id="t-1", status="queued", message="Queued.")

    def status(self, job_id: str) -> TrainingJob:
        return TrainingJob(id=job_id, status=self._status, message=self._message, adapter_ref=self._adapter_ref)


def _providers(trainer=None, sys1=None, jev=None) -> Providers:
    llm = FakeLLM([])
    return Providers(
        jev=jev or FakeDecisionProvider("jev", "jev-fake"),
        sys1=sys1,
        llm=llm,
        trainer=trainer or PreviewTrainer(duration_s=0),
        generator=SimpleGenerator(llm),
    )


def _project(client, per_bucket: int = 30) -> str:
    pid = client.post("/api/projects", json={"name": "Triage"}).json()["id"]
    policy = {"decision_question": "Where does it go?", "options": OPTIONS}
    assert client.put(f"/api/projects/{pid}/policy", json={"policy": policy}).status_code == 200
    _add(client, pid, {"billing": per_bucket, "shipping": per_bucket})
    return pid


def _add(client, pid: str, counts: dict[str, int], source="generated") -> None:
    with Session(client.app.state.engine) as session:
        project = session.get(Project, pid)
        rows = [NewExample(f"{key} issue number {i}", key, source) for key, n in counts.items() for i in range(n)]
        dataset_service.add_examples(session, project, rows)


def _train(client, pid: str) -> dict:
    res = client.post(f"/api/projects/{pid}/training")
    assert res.status_code == 200, res.text
    job_id = res.json()["job_id"]
    wait_for_job(job_id)
    return client.get(f"/api/jobs/{job_id}").json()


def _rows(report: dict) -> dict[str, dict]:
    return {r["key"]: r for r in report["rows"]}


def test_accuracy_ci_brackets_point_estimate():
    correct = [True] * 70 + [False] * 30
    acc, low, high = accuracy_ci(correct)
    assert acc == 0.7 and low < acc < high and 0.6 < low and high < 0.8
    assert accuracy_ci(correct) == (acc, low, high)  # seeded: same answer every time
    assert accuracy_ci([]) == (0.0, 0.0, 0.0)

    diff, low, high = paired_diff_ci([True] * 80 + [False] * 20, [True] * 50 + [False] * 50)
    assert diff == 0.3 and 0 < low < diff < high

    same, low, high = paired_diff_ci([True, False] * 30, [False, True] * 30)
    assert same == 0 and low < 0 < high

    assert per_bucket_accuracy(["a", "a", "b"], ["a", "b", "b"]) == {"a": 0.5, "b": 1.0}
    assert top_confusions(["a", "a", "a", "b"], ["b", "b", "a", "a"], k=1) == [("a", "b", 2)]


def test_preview_training_card_has_real_jev_rows_and_preview_sys1(client_for):
    jev = CountingJev()
    client = client_for("org_a", providers=_providers(jev=jev))
    pid = _project(client)
    assert client.get(f"/api/projects/{pid}/report").json()["available"] is False

    job = _train(client, pid)
    assert job["kind"] == "training" and job["status"] == "preview" and job["progress"] == 1.0
    assert job["result"]["skipped_stale"] == 0

    report = client.get(f"/api/projects/{pid}/report").json()
    rows = _rows(report)
    assert list(rows) == ["sys1", "jev", "jev_labels"]  # no base model for a project without one
    assert rows["sys1"]["status"] == "preview" and rows["sys1"]["message"] == "Real training connects soon."
    assert rows["sys1"]["accuracy"] is None
    assert rows["jev"]["status"] == "ok" and rows["jev"]["accuracy"] == 1.0 and rows["jev"]["n"] == 12
    assert rows["jev_labels"]["accuracy"] == 1.0
    assert report["is_preview"] and not report["is_fixture"] and report["test_set_version"] == 1
    assert report["verdict"]["winner"] == "none"
    assert report["details"]["per_bucket"]["jev"] == {"billing": 1.0, "shipping": 1.0}
    assert jev.calls == 24

    with Session(client.app.state.engine) as session:
        decisions = list(session.scalars(select(Decision).where(Decision.project_id == pid)))
        assert len(decisions) == 24 and {d.source for d in decisions} == {"eval"}
        assert all(d.not_for_training for d in decisions)
        assert session.scalar(select(TokenUsage.tokens)) is None  # Jev calls don't touch the Anthropic cap
        assert session.scalar(select(ReportCard.is_preview)) is True

    # The same versions are scored once: a second card re-uses the saved Jev answers.
    _train(client, pid)
    assert jev.calls == 24
    with Session(client.app.state.engine) as session:
        assert len(list(session.scalars(select(ReportCard)))) == 2
        assert len(list(session.scalars(select(JevEval)))) == 2


def test_jev_errors_hide_the_verdict_when_many(client_for):
    class GuidelinesDown(FakeDecisionProvider):
        """Fails the lane that sends guidelines (its instructions are an object), answers the bucket-only one."""

        async def decide(self, req: DecisionRequest):
            if isinstance(req.questions["decision"]["instructions"], dict):
                raise ProviderError("Jev is down.", retryable=True)
            return await super().decide(req)

    client = client_for("org_a", providers=_providers(jev=GuidelinesDown("jev", "jev-fake")))
    pid = _project(client)
    job = _train(client, pid)
    assert job["status"] == "preview"  # Jev trouble doesn't fail the run: the card says so instead
    report = client.get(f"/api/projects/{pid}/report").json()
    rows = _rows(report)
    assert rows["jev"]["status"] == "errored" and rows["jev"]["accuracy"] is None
    assert rows["jev"]["message"] == "Jev errored on 12 of 12" and rows["jev"]["errors"] == 12
    assert rows["jev_labels"]["accuracy"] == 1.0
    assert report["verdict"]["winner"] == "none" and "Jev" in report["verdict"]["sentence"]


def test_a_few_jev_errors_count_as_wrong(client_for):
    class SomeDown(FakeDecisionProvider):
        def __init__(self, name: str, model_label: str):
            super().__init__(name, model_label)
            self.failing: set[str] = set()

        async def decide(self, req: DecisionRequest):
            if req.state in self.failing:
                raise ProviderError("Jev is down.")
            return await super().decide(req)

    jev = SomeDown("jev", "jev-fake")
    client = client_for("org_a", providers=_providers(jev=jev))
    pid = _project(client)
    # The test examples are chosen by hash, so find which ones to fail after the freeze has picked them.
    with Session(client.app.state.engine) as session:
        project = session.get(Project, pid)
        dataset_service.freeze(session, project)
        tests = [e.input_json for e in session.scalars(select(Example).where(Example.split == "test"))]
    jev.failing = set(tests[:2])
    _train(client, pid)
    row = _rows(client.get(f"/api/projects/{pid}/report").json())["jev"]
    assert row["status"] == "ok" and row["errors"] == 2 and row["message"] == "Jev errored on 2 of 12"
    assert row["accuracy"] == pytest.approx(10 / 12)  # a failed answer counts as wrong


def test_training_freezes_and_copies_eligible_feedback(client_for):
    client = client_for("org_a", providers=_providers(sys1=FakeDecisionProvider("sys1", "sys1-fake")))
    pid = _project(client)
    pool = lambda: client.get(f"/api/projects/{pid}/training-pool").json()["count"]

    lanes = client.post(f"/api/projects/{pid}/try", json={"text": "my card was charged twice"}).json()["results"]
    sys1_decision = next(r["decision_id"] for r in lanes if r["lane"] == "sys1")
    jev_decision = next(r["decision_id"] for r in lanes if r["lane"] == "jev")
    client.post(f"/api/decisions/{sys1_decision}/feedback", json={"kind": "correction", "correct_label": "billing"})
    stale = client.post(f"/api/projects/{pid}/try", json={"text": "where is my parcel"}).json()["results"]
    stale_id = next(r["decision_id"] for r in stale if r["lane"] == "sys1")
    client.post(f"/api/decisions/{stale_id}/feedback", json={"kind": "correction", "correct_label": "shipping"})
    client.post(f"/api/decisions/{jev_decision}/feedback", json={"kind": "confirm"})  # never eligible
    assert pool() == 2
    with Session(client.app.state.engine) as session:
        assert session.get(Project, pid).frozen_at is None
        # The bucket this correction pointed at has since been removed from the policy.
        feedback = session.scalars(select(Feedback).where(Feedback.decision_id == stale_id)).one()
        feedback.correct_label = "gone"
        session.commit()

    job = _train(client, pid)
    assert job["result"]["copied"] == 1 and job["result"]["skipped_stale"] == 1
    with Session(client.app.state.engine) as session:
        project = session.get(Project, pid)
        assert project.frozen_at is not None and project.test_set_version == 1
        corrected = list(session.scalars(select(Example).where(Example.source == "corrected")))
        assert [(e.input_json, e.label) for e in corrected] == [("my card was charged twice", "billing")]
        assert corrected[0].split in ("train", "cal")  # a correction never lands in test
        assert project.dataset_version >= 2
    assert pool() == 0  # nothing new since the training started

    # Retraining neither copies the same correction twice nor loses count of the stale one.
    again = _train(client, pid)
    assert again["result"]["copied"] == 0 and again["result"]["skipped_stale"] == 1
    with Session(client.app.state.engine) as session:
        assert len(list(session.scalars(select(Example).where(Example.source == "corrected")))) == 1

    later = client.post(f"/api/projects/{pid}/try", json={"text": "another billing thing"}).json()["results"]
    later_id = next(r["decision_id"] for r in later if r["lane"] == "sys1")
    client.post(f"/api/decisions/{later_id}/feedback", json={"kind": "confirm"})
    assert pool() == 1


def test_trainer_receives_dataset_ref_and_config(client_for):
    trainer = FinishingTrainer("preview", "Real training connects soon.")
    client = client_for("org_a", providers=_providers(trainer=trainer))
    pid = _project(client)
    _train(client, pid)
    ref, config = trainer.started_with
    assert ref.startswith(f"project:{pid}:v") and config == {"project_id": pid, "test_set_version": 1}


def test_too_few_test_verdict(client_for):
    trainer = FinishingTrainer("succeeded", adapter_ref="adapter/1")
    client = client_for("org_a", providers=_providers(trainer=trainer, sys1=FirstOptionProvider()))
    pid = _project(client)  # 30 per bucket gives 6 test examples per bucket, under the 10 needed
    _train(client, pid)
    report = client.get(f"/api/projects/{pid}/report").json()
    assert report["too_few_test"] is True and not report["is_preview"]
    assert report["verdict"]["winner"] == "none"
    assert report["verdict"]["sentence"].startswith("Too few test examples for a firm verdict")
    sys1 = _rows(report)["sys1"]
    assert sys1["status"] == "ok" and sys1["accuracy"] == 0.5 and sys1["ci_low"] is not None


def test_verdict_names_a_winner_with_enough_test_examples(client_for):
    trainer = FinishingTrainer("succeeded", adapter_ref="adapter/1")
    client = client_for("org_a", providers=_providers(trainer=trainer, sys1=FirstOptionProvider()))
    pid = _project(client, per_bucket=50)
    _train(client, pid)
    report = client.get(f"/api/projects/{pid}/report").json()
    assert report["too_few_test"] is False
    assert report["verdict"]["winner"] == "jev" and report["verdict"]["diff"] < 0
    assert "Jev" in report["verdict"]["sentence"]


def test_sys1_row_is_unavailable_when_nothing_serves_the_model(client_for):
    trainer = FinishingTrainer("succeeded", adapter_ref="adapter/1")
    client = client_for("org_a", providers=_providers(trainer=trainer, sys1=None))
    pid = _project(client)
    _train(client, pid)
    sys1 = _rows(client.get(f"/api/projects/{pid}/report").json())["sys1"]
    assert sys1["status"] == "unavailable" and sys1["accuracy"] is None


def test_unavailable_trainer_still_gives_a_card_with_jev_rows(client_for):
    note = "Training isn't connected yet."
    client = client_for("org_a", providers=_providers(trainer=FinishingTrainer("unavailable", note)))
    pid = _project(client)
    job = _train(client, pid)
    assert job["status"] == "succeeded"
    report = client.get(f"/api/projects/{pid}/report").json()
    rows = _rows(report)
    assert rows["sys1"]["status"] == "unavailable" and rows["sys1"]["message"] == note
    assert rows["jev"]["accuracy"] == 1.0 and not report["is_preview"]


def test_failed_trainer_fails_the_job_with_its_message(client_for):
    client = client_for("org_a", providers=_providers(trainer=FinishingTrainer("failed", "Out of GPU hours.")))
    pid = _project(client)
    job = _train(client, pid)
    assert job["status"] == "failed" and job["message"] == "Out of GPU hours."
    assert client.get(f"/api/projects/{pid}/report").json()["available"] is False


def test_below_minimum_refused_422(client_for):
    client = client_for("org_a", providers=_providers())
    other = client.post("/api/projects", json={"name": "Thin"}).json()["id"]
    client.put(f"/api/projects/{other}/policy", json={"policy": {"decision_question": "Q", "options": OPTIONS}})
    _add(client, other, {"billing": 31, "shipping": 5})

    res = client.post(f"/api/projects/{other}/training")
    assert res.status_code == 422
    assert res.json()["detail"]["message"] == "Add at least 30 examples to: Shipping."
    with Session(client.app.state.engine) as session:
        assert session.get(Project, other).frozen_at is None
        assert session.scalar(select(Job.id).where(Job.project_id == other)) is None


def test_unfinished_buckets_and_running_job_refused(client_for):
    client = client_for("org_a", providers=_providers())
    blank = client.post("/api/projects", json={"name": "Blank"}).json()["id"]
    assert client.post(f"/api/projects/{blank}/training").status_code == 422

    pid = _project(client)
    with Session(client.app.state.engine) as session:
        session.add(Job(org_id="org_a", project_id=pid, kind="training", status="running"))
        session.commit()
    res = client.post(f"/api/projects/{pid}/training")
    assert res.status_code == 409 and res.json()["detail"]["code"] == "training_running"


def test_other_org_404_report(client_for):
    owner = client_for("org_a", providers=_providers())
    pid = _project(owner)
    _train(owner, pid)
    other = client_for("org_b", engine=owner.app.state.engine)
    assert other.get(f"/api/projects/{pid}/report").status_code == 404
    assert other.post(f"/api/projects/{pid}/training").status_code == 404

    assert owner.delete(f"/api/projects/{pid}").status_code == 204
    with Session(owner.app.state.engine) as session:
        assert session.scalar(select(ReportCard.id)) is None and session.scalar(select(JevEval.id)) is None


def test_flagship_serves_its_recorded_card(client_for):
    client = client_for("org_a", providers=_providers())
    pid = client.post("/api/projects", json={"name": "Tallyfern", "template_id": FLAGSHIP}).json()["id"]
    report = client.get(f"/api/projects/{pid}/report").json()
    assert report["available"] and report["is_fixture"] and not report["is_preview"]
    rows = _rows(report)
    assert list(rows) == ["sys1", "jev", "jev_labels", "base"]
    assert rows["jev"]["accuracy"] == pytest.approx(0.7166666, abs=1e-4) and rows["jev"]["n"] == 60
    assert report["verdict"]["winner"] in ("sys1", "jev", "inconclusive")
    assert report["details"]["per_bucket"]["sys1"]


async def test_preview_trainer_unknown_job_does_not_invent_one():
    trainer = PreviewTrainer(duration_s=0)
    unknown = trainer.status("nope")
    assert unknown.status == "failed" and unknown.message == "Unknown job."
    assert trainer._jobs == {}
    assert trainer.start("a", {}).id != trainer.start("a", {}).id


def test_confirmed_training_action_starts_the_same_job(client_for):
    from system1.agent.models import PendingAction

    client = client_for("org_a", providers=_providers())
    pid = _project(client)
    with Session(client.app.state.engine) as session:
        action = PendingAction(project_id=pid, org_id="org_a", kind="training", params_json={})
        session.add(action)
        session.commit()
        action_id = action.id
    res = client.post(f"/api/projects/{pid}/actions/{action_id}/confirm")
    assert res.status_code == 200, res.text
    job_id = res.json()["result"]["job_id"]
    wait_for_job(job_id)
    assert client.get(f"/api/jobs/{job_id}").json()["kind"] == "training"
    assert client.get(f"/api/projects/{pid}/report").json()["available"] is True
