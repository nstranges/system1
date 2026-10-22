from typing import Annotated, Literal

from pydantic import BaseModel, Field

from system1.domain.policy import Policy
from system1.gateway.service import TryResult


class UserEvent(BaseModel):
    # Only appears when replaying history; live streams carry the assistant's side.
    type: Literal["user"] = "user"
    text: str


class TextEvent(BaseModel):
    type: Literal["text"] = "text"
    delta: str


class ToolEvent(BaseModel):
    type: Literal["tool"] = "tool"
    name: str
    status: Literal["started", "done", "error"]
    summary: str = ""


class ChoicesEvent(BaseModel):
    type: Literal["choices"] = "choices"
    question: str
    options: list[str] = Field(min_length=2, max_length=4)


class FitEvent(BaseModel):
    type: Literal["fit"] = "fit"
    rating: Literal["good", "workable", "poor"]
    reasons: list[str]


class CanvasEvent(BaseModel):
    type: Literal["canvas"] = "canvas"
    policy: Policy
    version: int
    changed: list[str]


class TryResultEvent(BaseModel):
    type: Literal["try_result"] = "try_result"
    input: str
    result: TryResult


class ConfirmEvent(BaseModel):
    type: Literal["confirm"] = "confirm"
    action_id: str
    kind: Literal["dataset", "training"]
    title: str
    detail: str
    est_minutes: float
    est_cost_usd: float


class StageEvent(BaseModel):
    type: Literal["stage"] = "stage"
    stage: str


class ErrorEvent(BaseModel):
    type: Literal["error"] = "error"
    message: str


class DoneEvent(BaseModel):
    type: Literal["done"] = "done"


AgentEvent = Annotated[
    UserEvent
    | TextEvent
    | ToolEvent
    | ChoicesEvent
    | FitEvent
    | CanvasEvent
    | TryResultEvent
    | ConfirmEvent
    | StageEvent
    | ErrorEvent
    | DoneEvent,
    Field(discriminator="type"),
]
