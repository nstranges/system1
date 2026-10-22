import asyncio
import time

import httpx
from pydantic import ValidationError

from system1.contracts.decisions import DecisionRequest, DecisionResponse, ProviderError

MAX_RETRIES = 3
RETRYABLE = {429, 529}


class TypeSafeJevProvider:
    """Calls a Jev-compatible `POST {base_url}/v1/systemone` endpoint."""

    name = "jev"
    label = "Jev"
    requires_key = True
    not_configured = "Jev isn't configured on this server"
    busy = "Jev is busy right now. Try again in a moment."

    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        model: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        backoff_base: float = 0.5,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self._transport = transport
        self._backoff_base = backoff_base

    async def decide(self, req: DecisionRequest) -> DecisionResponse:
        if self.api_key is None and self.requires_key:
            raise ProviderError(self.not_configured)
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        body = req.model_dump(mode="json")
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=30.0, transport=self._transport) as client:
            for attempt in range(MAX_RETRIES + 1):
                try:
                    resp = await client.post(f"{self.base_url}/v1/systemone", json=body, headers=headers)
                except httpx.TransportError as exc:
                    if attempt == MAX_RETRIES:
                        raise ProviderError(self.busy, retryable=True) from exc
                else:
                    if resp.status_code in RETRYABLE or resp.status_code >= 500:
                        if attempt == MAX_RETRIES:
                            raise ProviderError(self.busy, retryable=True, status=resp.status_code)
                    else:
                        return self._parse(resp, (time.perf_counter() - started) * 1000)
                await asyncio.sleep(self._backoff_base * 2**attempt)
        raise AssertionError("unreachable")  # the loop always returns or raises

    def _parse(self, resp: httpx.Response, latency_ms: float) -> DecisionResponse:
        if resp.status_code == 422:
            raise ProviderError(_detail(resp), status=422)
        if resp.status_code in (401, 403):
            raise ProviderError(f"{self.label} rejected the API key. Check TYPESAFE_API_KEY.", status=resp.status_code)
        if resp.status_code >= 400:
            raise ProviderError(f"{self.label} rejected the request ({resp.status_code}).", status=resp.status_code)
        try:
            data = resp.json()
            return DecisionResponse(
                model=data["model"], answers=data["answers"], usage=data.get("usage"), latency_ms=latency_ms
            )
        except (ValueError, KeyError, TypeError, ValidationError) as exc:
            raise ProviderError(f"{self.label} returned an unexpected response.", status=resp.status_code) from exc


def _detail(resp: httpx.Response) -> str:
    try:
        detail = resp.json().get("detail")
    except ValueError:
        detail = None
    if isinstance(detail, list):
        return "; ".join(str(d.get("msg", d)) if isinstance(d, dict) else str(d) for d in detail)
    return str(detail) if detail else "The request was rejected."
