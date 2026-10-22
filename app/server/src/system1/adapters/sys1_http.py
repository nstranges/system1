import httpx

from system1.adapters.jev_typesafe import TypeSafeJevProvider


class HttpSys1Provider(TypeSafeJevProvider):
    """sys1 behind any Jev-compatible server (such as laya-serve); the key is optional."""

    name = "sys1"
    label = "sys1"
    requires_key = False
    busy = "sys1 is busy right now. Try again in a moment."

    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        backoff_base: float = 0.5,
    ):
        super().__init__(base_url, api_key, model, transport=transport, backoff_base=backoff_base)
