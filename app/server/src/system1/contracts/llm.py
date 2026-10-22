from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass
class TextDelta:
    text: str


@dataclass
class TurnComplete:
    # Content blocks as plain dicts so they can be stored and replayed as the next assistant turn.
    content: list[dict]
    stop_reason: str
    input_tokens: int
    output_tokens: int


class LLM(Protocol):
    def stream_turn(
        self, *, system: list[dict], messages: list[dict], tools: list[dict]
    ) -> AsyncIterator[TextDelta | TurnComplete]: ...

    async def structured(self, *, system: str, prompt: str, schema: type[T], max_tokens: int = 4000) -> tuple[T, int]:
        """Return the parsed result and the tokens used."""
        ...
