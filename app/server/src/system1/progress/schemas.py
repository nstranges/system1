from typing import Literal

from pydantic import BaseModel

StageId = Literal["define", "data", "review", "train", "use", "improve"]


class StageState(BaseModel):
    id: StageId
    status: Literal["done", "ready", "blocked"]
    note: str


class ProjectProgress(BaseModel):
    # Always six, in journey order.
    stages: list[StageState]
    # The first stage that is ready to be worked on, if any.
    next: StageId | None
    examples: int
    # The latest report card's accuracy for your model and for Jev with your guidelines, 0 to 1.
    accuracy: float | None
    jev_accuracy: float | None
