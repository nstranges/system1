from typing import Literal, Protocol

from pydantic import BaseModel


class DatasetRow(BaseModel):
    id: str
    split: Literal["train", "cal", "test"]
    state: str | dict | list
    questions: dict
    gold: dict[str, str]
    metadata: dict = {}


class DatasetSource(Protocol):
    def rows(self, split: str | None = None) -> list[DatasetRow]: ...
