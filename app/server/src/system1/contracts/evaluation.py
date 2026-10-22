from typing import Protocol

from pydantic import BaseModel


class EvalRecord(BaseModel):
    id: str
    question: str
    pred: str
    gold: str
    confidence: float | None = None
    p_gold: float | None = None
    correct: bool


class EvalRun(BaseModel):
    model_key: str
    label: str
    summary: dict
    records: list[EvalRecord]
    is_fixture: bool


class EvalResultsSource(Protocol):
    def runs(self) -> list[EvalRun]: ...
