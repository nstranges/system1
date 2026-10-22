from typing import Literal, Protocol

from pydantic import BaseModel


class DecisionRequest(BaseModel):
    model: str
    state: str | dict | list
    questions: dict[str, dict]


class ChoiceAnswer(BaseModel):
    type: Literal["choice"]
    choice: str
    # Jev and Laya define confidence differently; calibration must use `probabilities`.
    confidence: float | None = None
    probabilities: dict[str, float]


class DecisionResponse(BaseModel):
    model: str
    answers: dict[str, ChoiceAnswer]
    usage: dict | None = None
    latency_ms: float


class ProviderError(Exception):
    def __init__(self, user_message: str, *, retryable: bool = False, status: int | None = None):
        super().__init__(user_message)
        self.user_message = user_message
        self.retryable = retryable
        self.status = status


class DecisionProvider(Protocol):
    name: str

    async def decide(self, req: DecisionRequest) -> DecisionResponse: ...
