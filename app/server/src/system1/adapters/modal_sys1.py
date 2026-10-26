import asyncio
import json
import time
from typing import Protocol

from system1.contracts.decisions import ChoiceAnswer, DecisionRequest, DecisionResponse, ProviderError

FAILED = "Your model didn't answer. Try again in a moment."
# The first call after the model has gone cold loads Laya and the adapter, which takes up to a minute or so.
COLD_START_S = 180.0


class DeciderRunner(Protocol):
    """The slice of Modal the provider needs, so tests don't need Modal."""

    async def decide(self, adapter_ref: str, state: str, questions: dict) -> dict:
        """{"answers": {question: {"type", "choice", "confidence", "probabilities"}}}"""
        ...


class SdkDeciderRunner:
    """Calls the `Decider` class deployed by `make modal-deploy`. Needs Modal's own auth."""

    def __init__(self, app_name: str, class_name: str):
        self._app_name, self._class_name = app_name, class_name

    async def decide(self, adapter_ref: str, state: str, questions: dict) -> dict:
        import modal

        decider = modal.Cls.from_name(self._app_name, self._class_name)()
        return await decider.decide.remote.aio(adapter_ref, state, questions)


class ModalSys1Provider:
    """sys1 on Modal: answers with whichever trained adapter the request's `model` names (a run's adapter_ref)."""

    name = "sys1"
    label = "sys1"
    serves_adapters = True

    def __init__(self, runner: DeciderRunner, timeout_s: float = COLD_START_S):
        self._runner = runner
        self._timeout_s = timeout_s

    async def decide(self, req: DecisionRequest) -> DecisionResponse:
        # Training saw each example's input as text, or as JSON text for structured input; send it the same way.
        state = req.state if isinstance(req.state, str) else json.dumps(req.state)
        started = time.perf_counter()
        try:
            result = await asyncio.wait_for(self._runner.decide(req.model, state, req.questions), self._timeout_s)
        # Broad on purpose: besides our timeout, Modal re-raises an error from inside the remote call as its own type.
        except Exception as exc:
            raise ProviderError(FAILED, retryable=True) from exc
        # The round trip from here, not just the model's own time, so it compares fairly with Jev's.
        latency_ms = (time.perf_counter() - started) * 1000
        return DecisionResponse(
            model="sys1",
            answers={k: ChoiceAnswer(**v) for k, v in result.get("answers", {}).items()},
            usage=None,
            latency_ms=latency_ms,
        )
