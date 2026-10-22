from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Request

from system1.adapters.anthropic_llm import AnthropicLLM
from system1.adapters.fakes import FakeDecisionProvider, FakeLLM, FakeTrainer, PreviewTrainer, UnavailableTrainer
from system1.adapters.jev_typesafe import TypeSafeJevProvider
from system1.adapters.sys1_http import HttpSys1Provider
from system1.config import Settings
from system1.contracts.decisions import DecisionProvider
from system1.contracts.llm import LLM
from system1.contracts.training import Trainer


@dataclass
class Providers:
    jev: DecisionProvider
    sys1: DecisionProvider | None
    llm: LLM
    trainer: Trainer


def build_providers(settings: Settings) -> Providers:
    if settings.jev_provider == "fake":
        jev: DecisionProvider = FakeDecisionProvider("jev", settings.jev_model)
    else:
        jev = TypeSafeJevProvider(settings.typesafe_base_url, settings.typesafe_api_key, settings.jev_model)

    sys1: DecisionProvider | None = None
    if settings.sys1_provider == "fake":
        sys1 = FakeDecisionProvider("sys1", settings.sys1_model)
    elif settings.sys1_provider == "http" and settings.sys1_base_url:
        sys1 = HttpSys1Provider(settings.sys1_base_url, settings.sys1_model)

    if settings.llm_provider == "fake":
        llm: LLM = FakeLLM([])
    else:
        llm = AnthropicLLM(settings.anthropic_api_key, settings.agent_model, settings.agent_effort)

    trainers: dict[str, Callable[[], Trainer]] = {
        "fake": FakeTrainer,
        "preview": PreviewTrainer,
        "none": UnavailableTrainer,
    }
    trainer = trainers[settings.trainer]()
    return Providers(jev=jev, sys1=sys1, llm=llm, trainer=trainer)


def get_providers(request: Request) -> Providers:
    return request.app.state.providers
