from typing import Literal, Protocol

from pydantic import BaseModel


class EvalAnswer(BaseModel):
    """One model answer on a frozen test example. The server scores it against its own copy of the gold label."""

    id: str
    pred: str | None = None
    p_gold: float | None = None
    latency_ms: float | None = None


class TrainingJob(BaseModel):
    id: str
    status: Literal["queued", "running", "succeeded", "failed", "unavailable", "preview"]
    message: str
    adapter_ref: str | None = None
    metrics: dict = {}
    # Answers on the test examples by row ("sys1", "base"), for trainers that also score what they trained.
    evaluations: dict[str, list[EvalAnswer]] = {}


class Trainer(Protocol):
    """A trainer with `needs_examples = True` also gets `config["questions"]` (the question it is trained to answer)
    and `config["examples"]` (`{id, split, input, label}` for every example, test split included: it may only
    score on test, never train on it)."""

    def start(self, dataset_ref: str, config: dict) -> TrainingJob: ...

    def status(self, job_id: str) -> TrainingJob: ...
