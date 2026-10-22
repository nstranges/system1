"""Scores a model on a project's frozen test examples by asking it each one through the gateway.

Jev's answers are kept per test set and set of guidelines (`jev_evals`), so a second report card on the same
versions doesn't call Jev again. Jev calls never count against the Anthropic token cap.
"""

import asyncio
from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from system1.datasets.models import Example
from system1.domain.policy import Policy
from system1.errors import ApiError
from system1.gateway.service import run_lane
from system1.projects.models import Project
from system1.projects.service import latest_policy
from system1.providers import Providers
from system1.report.models import JevEval

JEV_LANES: tuple[Literal["jev", "jev_labels"], ...] = ("jev", "jev_labels")
MAX_IN_FLIGHT = 4


class PredRecord(BaseModel):
    id: str
    gold: str
    pred: str | None = None
    p_gold: float | None = None
    latency_ms: float | None = None
    correct: bool = False
    # Why the model gave no answer. Such an example counts as wrong.
    error: str | None = None


def load_test_examples(session: Session, project: Project) -> list[Example]:
    return list(
        session.scalars(
            select(Example).where(Example.project_id == project.id, Example.split == "test").order_by(Example.id)
        )
    )


def _cached(
    session: Session, project: Project, test_set_version: int, policy_version: int, lane: str
) -> JevEval | None:
    return session.scalars(
        select(JevEval).where(
            JevEval.project_id == project.id,
            JevEval.test_set_version == test_set_version,
            JevEval.policy_version == policy_version,
            JevEval.lane == lane,
        )
    ).first()


async def evaluate_lane(
    session: Session,
    providers: Providers,
    project: Project,
    lane: Literal["jev", "jev_labels", "sys1"],
    test_set_version: int,
    *,
    policy_and_version: tuple[Policy, int] | None = None,
    use_cache: bool = False,
    on_done: Callable[[], None] | None = None,
    gate: asyncio.Semaphore | None = None,
) -> list[PredRecord]:
    policy, policy_version = policy_and_version or latest_policy(session, project)
    examples = load_test_examples(session, project)
    cache_row = _cached(session, project, test_set_version, policy_version, lane) if use_cache else None
    saved: dict[str, dict] = dict(cache_row.results_json) if cache_row else {}
    fetched: dict[str, dict | str] = {}  # example id -> answer, or the reason there was none
    gate = gate or asyncio.Semaphore(MAX_IN_FLIGHT)

    async def ask(example: Example) -> None:
        async with gate:
            try:
                result = await run_lane(
                    session,
                    providers,
                    project,
                    example.input_json,
                    lane,
                    "eval",
                    policy_and_version=(policy, policy_version),
                )
            except ApiError as exc:  # e.g. an input over the length limit: it counts as wrong, the rest still run
                fetched[example.id] = exc.message
            else:
                if result.error or result.label is None:
                    fetched[example.id] = result.error or "No answer."
                else:
                    fetched[example.id] = {
                        "label": result.label,
                        "p_gold": result.probabilities.get(example.label),
                        "latency_ms": result.latency_ms,
                    }
        if on_done:
            on_done()

    todo = [e for e in examples if e.id not in saved]
    if on_done:
        for _ in range(len(examples) - len(todo)):
            on_done()
    await asyncio.gather(*(ask(e) for e in todo))

    new = {k: v for k, v in fetched.items() if isinstance(v, dict)}
    if use_cache and new:
        merged = {**saved, **new}
        if cache_row is None:
            session.add(
                JevEval(
                    project_id=project.id,
                    test_set_version=test_set_version,
                    policy_version=policy_version,
                    lane=lane,
                    results_json=merged,
                )
            )
        else:
            cache_row.results_json = merged
        session.commit()

    records = []
    for example in examples:
        answer = saved.get(example.id) or fetched.get(example.id)
        if isinstance(answer, dict):
            records.append(
                PredRecord(
                    id=example.id,
                    gold=example.label,
                    pred=answer["label"],
                    p_gold=answer.get("p_gold"),
                    latency_ms=answer.get("latency_ms"),
                    correct=answer["label"] == example.label,
                )
            )
        else:
            records.append(PredRecord(id=example.id, gold=example.label, error=answer or "No answer."))
    return records


async def evaluate_jev(
    session: Session,
    providers: Providers,
    project: Project,
    test_set_version: int,
    *,
    policy_and_version: tuple[Policy, int] | None = None,
    on_progress: Callable[[float], None] | None = None,
) -> dict[str, list[PredRecord]]:
    """Jev with the guidelines (`jev`) and with bucket names only (`jev_labels`), on every test example."""
    policy_and_version = policy_and_version or latest_policy(session, project)
    total = len(load_test_examples(session, project)) * len(JEV_LANES)
    done = 0
    gate = asyncio.Semaphore(MAX_IN_FLIGHT)  # shared, so both lanes together keep at most this many calls in flight

    def tick() -> None:
        nonlocal done
        done += 1
        if on_progress:
            on_progress(done / total)

    results = await asyncio.gather(
        *(
            evaluate_lane(
                session,
                providers,
                project,
                lane,
                test_set_version,
                policy_and_version=policy_and_version,
                use_cache=True,
                on_done=tick,
                gate=gate,
            )
            for lane in JEV_LANES
        )
    )
    return dict(zip(JEV_LANES, results, strict=True))
