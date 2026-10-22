from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from system1.domain.policy import Policy


@dataclass
class GeneratedExample:
    input: str
    label: str
    # The probability the blind check gave the bucket the example was written for.
    # None when the blind check returned nothing for this input.
    how_sure: float | None


class ExampleGenerator(Protocol):
    async def generate(
        self,
        policy: Policy,
        context: str,
        samples: list[str],
        targets: dict[str, int],
        on_progress: Callable[[float], None],
        before_batch: Callable[[], None] | None = None,
        on_batch: Callable[[list[GeneratedExample], int], int | None] | None = None,
    ) -> tuple[list[GeneratedExample], int]:
        """Return every example written and the tokens used.

        `before_batch` runs ahead of each batch and may raise to stop the run. `on_batch` receives each
        finished batch and its tokens, so a caller can save work as it lands and keep it if a later batch fails.
        It may return how many examples were actually kept, which is what counts toward the bucket's target.
        """
        ...
