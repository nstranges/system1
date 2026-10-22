from collections.abc import AsyncIterator

from anthropic import AsyncAnthropic

from system1.contracts.llm import T, TextDelta, TurnComplete

# Opus 5.5 can refuse on safety classifiers; "default" lets the API re-run the request on the
# model it recommends for the refusal category instead of us maintaining a list.
_BETAS = ["server-side-fallback-2026-07-01"]


class AnthropicLLM:
    def __init__(self, api_key: str | None, model: str, effort: str):
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model
        self._effort = effort

    async def stream_turn(
        self, *, system: list[dict], messages: list[dict], tools: list[dict]
    ) -> AsyncIterator[TextDelta | TurnComplete]:
        # Thinking can't be disabled on Opus 5.5, so `thinking` is omitted; no forced tool_choice, no prefill.
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
        yield TurnComplete(
            content=[block.model_dump(mode="json", exclude_none=True) for block in final.content],
            stop_reason=final.stop_reason or "end_turn",
            input_tokens=final.usage.input_tokens,
            output_tokens=final.usage.output_tokens,
        )

    async def structured(self, *, system: str, prompt: str, schema: type[T], max_tokens: int = 4000) -> tuple[T, int]:
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
        if response.parsed_output is None:
            raise ValueError(f"The model returned no structured output (stop_reason={response.stop_reason}).")
        return response.parsed_output, response.usage.input_tokens + response.usage.output_tokens
