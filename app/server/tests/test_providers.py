import os

import httpx
import pytest

from system1.adapters.fakes import FakeDecisionProvider
from system1.adapters.jev_typesafe import TypeSafeJevProvider
from system1.contracts.decisions import DecisionRequest, DecisionResponse, ProviderError

JEV_RESPONSE = {
    "model": "jev-1.13.0",
    "answers": {
        "queue": {
            "type": "choice",
            "choice": "billing_refunds",
            "confidence": 0.7,
            "probabilities": {"billing_refunds": 0.8, "billing_disputes": 0.2},
        }
    },
    "usage": {"input_tokens": 120, "output_tokens": 12},
}

REQUEST = DecisionRequest(
    model="jev-1.13.0",
    state="Please refund the add-on we were charged for.",
    questions={
        "queue": {
            "type": "choice",
            "instructions": "Which team should handle this ticket?",
            "criteria": {"billing_refunds": "Refund requests within policy", "billing_disputes": None},
        }
    },
)


def jev(handler, api_key: str | None = "key") -> TypeSafeJevProvider:
    return TypeSafeJevProvider(
        base_url="https://jev.test",
        api_key=api_key,
        model="jev-1.13.0",
        transport=httpx.MockTransport(handler),
        backoff_base=0,
    )


async def test_fake_and_jev_adapter_parse_the_same_response():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=JEV_RESPONSE)

    real = await jev(handler).decide(REQUEST)
    fake = await FakeDecisionProvider("fake", "fake-1").decide(REQUEST)

    assert type(real) is type(fake) is DecisionResponse
    assert real.answers["queue"].choice == "billing_refunds"
    assert real.model == "jev-1.13.0"
    assert real.answers["queue"].probabilities["billing_refunds"] == 0.8
    assert real.latency_ms >= 0
    assert seen[0].url == "https://jev.test/v1/systemone"
    assert seen[0].headers["authorization"] == "Bearer key"
    assert fake.answers["queue"].choice == "billing_refunds"


async def test_jev_429_then_success_retries():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, json={"detail": "slow down"})
        return httpx.Response(200, json=JEV_RESPONSE)

    result = await jev(handler).decide(REQUEST)
    assert calls == 2
    assert result.answers["queue"].choice == "billing_refunds"


async def test_jev_without_key_raises_provider_error_with_message():
    provider = jev(lambda request: httpx.Response(200, json=JEV_RESPONSE), api_key=None)
    with pytest.raises(ProviderError) as exc:
        await provider.decide(REQUEST)
    assert exc.value.user_message == "Jev isn't configured on this server"
    assert exc.value.retryable is False


async def test_jev_retries_exhausted_raises_busy_message():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(529)

    with pytest.raises(ProviderError) as exc:
        await jev(handler).decide(REQUEST)
    assert calls == 4  # the first try plus 3 retries
    assert exc.value.user_message == "Jev is busy right now. Try again in a moment."
    assert exc.value.retryable is True


async def test_jev_malformed_200_raises_provider_error():
    with pytest.raises(ProviderError) as exc:
        await jev(lambda request: httpx.Response(200, json={"oops": 1})).decide(REQUEST)
    assert exc.value.user_message == "Jev returned an unexpected response."


async def test_anthropic_llm_without_key_starts_but_raises_provider_error():
    from pydantic import BaseModel

    from system1.config import Settings
    from system1.providers import build_providers

    class Out(BaseModel):
        x: int

    providers = build_providers(Settings(_env_file=None, anthropic_api_key=None))
    with pytest.raises(ProviderError) as exc:
        await providers.llm.structured(system="s", prompt="p", schema=Out)
    assert exc.value.user_message == "The AI assistant isn't configured on this server."


@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("LIVE"), reason="calls the real Jev API; set LIVE=1")
async def test_jev_live_smoke():
    from system1.config import Settings

    settings = Settings()
    provider = TypeSafeJevProvider(settings.typesafe_base_url, settings.typesafe_api_key, settings.jev_model)
    options = {"billing_refunds": "Refund requests within policy", "billing_disputes": "Chargebacks and disputes"}
    result = await provider.decide(
        DecisionRequest(
            model=settings.jev_model,
            state="Hi, we were charged $544 for an add-on 22 days ago and want a refund.",
            questions={"queue": {"type": "choice", "instructions": "Which queue?", "criteria": options}},
        )
    )
    assert result.answers["queue"].choice in options
