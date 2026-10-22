import time
from collections import deque
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel

from system1.contracts.decisions import ChoiceAnswer, DecisionRequest, DecisionResponse
from system1.contracts.llm import T, TextDelta, TurnComplete
from system1.contracts.training import TrainingJob


class FakeDecisionProvider:
    """Picks the first option whose key appears in the state text, otherwise the first option."""

    def __init__(self, name: str, model_label: str):
        self.name = name
        self.model_label = model_label

    async def decide(self, req: DecisionRequest) -> DecisionResponse:
        started = time.perf_counter()
        text = (req.state if isinstance(req.state, str) else repr(req.state)).lower()
        answers: dict[str, ChoiceAnswer] = {}
        for qname, question in req.questions.items():
            options = list(question.get("criteria") or {})
            if not options:
                continue
            chosen = next((o for o in options if o.lower() in text), options[0])
            rest = [o for o in options if o != chosen]
            probs = {chosen: 0.9 if rest else 1.0}
            probs.update({o: 0.1 / len(rest) for o in rest})
            answers[qname] = ChoiceAnswer(type="choice", choice=chosen, confidence=probs[chosen], probabilities=probs)
        return DecisionResponse(
            model=self.model_label, answers=answers, usage=None, latency_ms=(time.perf_counter() - started) * 1000
        )


class FakeLLM:
    """Replays a script. A `stream_turn` call consumes a list of events; a `structured` call consumes
    a model instance (optionally as `(instance, tokens)`)."""

    def __init__(self, script: list[Any]):
        self._script = deque(script)
        self.calls: list[dict] = []

    async def stream_turn(
        self, *, system: list[dict], messages: list[dict], tools: list[dict]
    ) -> AsyncIterator[TextDelta | TurnComplete]:
        self.calls.append({"system": system, "messages": messages, "tools": tools})
        events = self._script.popleft()
        for event in events:
            yield event

    async def structured(self, *, system: str, prompt: str, schema: type[T], max_tokens: int = 4000) -> tuple[T, int]:
        self.calls.append({"system": system, "prompt": prompt, "schema": schema})
        item = self._script.popleft()
        result, tokens = item if isinstance(item, tuple) else (item, 0)
        if not isinstance(result, BaseModel):
            raise TypeError("FakeLLM structured script entries must be pydantic models")
        return result, tokens


class FakeTrainer:
    """Succeeds on the second `status` call for a job."""

    def __init__(self) -> None:
        self._polls: dict[str, int] = {}

    def start(self, dataset_ref: str, config: dict) -> TrainingJob:
        job_id = f"fake-job-{len(self._polls) + 1}"
        self._polls[job_id] = 0
        return TrainingJob(id=job_id, status="queued", message="Queued.")

    def status(self, job_id: str) -> TrainingJob:
        self._polls[job_id] = self._polls.get(job_id, 0) + 1
        if self._polls[job_id] < 2:
            return TrainingJob(id=job_id, status="running", message="Training.")
        return TrainingJob(
            id=job_id, status="succeeded", message="Done.", adapter_ref=f"fake-adapter/{job_id}", metrics={"loss": 0.1}
        )


class UnavailableTrainer:
    message = "Training isn't connected yet. The training pipeline runs separately for now."

    def start(self, dataset_ref: str, config: dict) -> TrainingJob:
        return TrainingJob(id="unavailable", status="unavailable", message=self.message)

    def status(self, job_id: str) -> TrainingJob:
        return TrainingJob(id=job_id, status="unavailable", message=self.message)
