from collections.abc import AsyncIterator

import anthropic
from anthropic import AsyncAnthropic

from system1.contracts.decisions import ProviderError
from system1.contracts.llm import T, TextDelta, TurnComplete

# Opus 5.5 can refuse on safety classifiers; "default" lets the API re-run the request on the
# model it recommends for the refusal category instead of us maintaining a list.
_BETAS = ["server-side-fallback-2026-07-01"]

OUT_OF_CREDITS = "The AI assistant is out of credits on this server, so this step can't run right now."
NOT_CONFIGURED = "The AI assistant isn't set up correctly on this server."
BUSY = "The AI assistant is busy right now. Wait a minute and try again."
UNAVAILABLE = "The AI assistant is unavailable right now. Try again in a moment."


def to_provider_error(exc: anthropic.APIError) -> ProviderError:
    """Turns an Anthropic SDK error into a message a person can act on, most specific first."""
    if isinstance(exc, anthropic.APIStatusError):
        # An empty balance comes back as billing_error (402), or on older accounts as a 400 that says so.
        if (
            exc.type == "billing_error"
            or exc.status_code == 402
            or (isinstance(exc, anthropic.BadRequestError) and "credit balance" in exc.message.lower())
        ):
            return ProviderError(OUT_OF_CREDITS, status=exc.status_code)
        if isinstance(exc, anthropic.AuthenticationError | anthropic.PermissionDeniedError | anthropic.NotFoundError):
            return ProviderError(NOT_CONFIGURED, status=exc.status_code)
        if isinstance(exc, anthropic.RateLimitError):
            return ProviderError(BUSY, retryable=True, status=exc.status_code)
        if exc.status_code >= 500:
            return ProviderError(UNAVAILABLE, retryable=True, status=exc.status_code)
        return ProviderError("The AI assistant couldn't handle that request.", status=exc.status_code)
    # Connection errors and timeouts: nothing came back, so trying again may work.
    return ProviderError(UNAVAILABLE, retryable=True)


class AnthropicLLM:
    def __init__(self, api_key: str | None, model: str, effort: str):
        self._api_key = api_key
        self._client_instance: AsyncAnthropic | None = None
        self._model = model
        self._effort = effort

    @property
    def _client(self) -> AsyncAnthropic:
        # Built on first use: the SDK raises at construction without a key, which must not stop the app starting.
        if not self._api_key:
            raise ProviderError("The AI assistant isn't configured on this server.")
        if self._client_instance is None:
            self._client_instance = AsyncAnthropic(api_key=self._api_key)
        return self._client_instance

    async def stream_turn(
        self, *, system: list[dict], messages: list[dict], tools: list[dict]
    ) -> AsyncIterator[TextDelta | TurnComplete]:
        # Thinking can't be disabled on Opus 5.5, so `thinking` is omitted; no forced tool_choice, no prefill.
        try:
            async with self._client.beta.messages.stream(
                model=self._model,
                max_tokens=16000,
                system=system,
                messages=messages,
                tools=tools,
                output_config={"effort": self._effort},
                betas=_BETAS,
                fallbacks="default",
            ) as stream:
                async for text in stream.text_stream:
                    yield TextDelta(text)
                final = await stream.get_final_message()
        except anthropic.APIError as exc:
            raise to_provider_error(exc) from exc
        yield TurnComplete(
            content=[block.model_dump(mode="json", exclude_none=True) for block in final.content],
            stop_reason=final.stop_reason or "end_turn",
            input_tokens=final.usage.input_tokens,
            output_tokens=final.usage.output_tokens,
        )

    async def structured(self, *, system: str, prompt: str, schema: type[T], max_tokens: int = 4000) -> tuple[T, int]:
        try:
            response = await self._client.beta.messages.parse(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                output_format=schema,
                output_config={"effort": self._effort},
                betas=_BETAS,
                fallbacks="default",
            )
        except anthropic.APIError as exc:
            raise to_provider_error(exc) from exc
        # A truncated or empty answer is the provider's failure, not a bug: it maps to 502/503 like any other.
        if response.stop_reason == "max_tokens" or response.parsed_output is None:
            raise ProviderError("The assistant's answer was cut off. Try again.", retryable=True)
        return response.parsed_output, response.usage.input_tokens + response.usage.output_tokens
