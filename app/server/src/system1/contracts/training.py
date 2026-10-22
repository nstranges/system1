from typing import Literal, Protocol

from pydantic import BaseModel


class TrainingJob(BaseModel):
    id: str
    status: Literal["queued", "running", "succeeded", "failed", "unavailable"]
    message: str
    adapter_ref: str | None = None
    metrics: dict = {}


class Trainer(Protocol):
    def start(self, dataset_ref: str, config: dict) -> TrainingJob: ...

    def status(self, job_id: str) -> TrainingJob: ...
