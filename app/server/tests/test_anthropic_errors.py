import anthropic
import httpx2
import pytest

from system1.adapters.anthropic_llm import BUSY, NOT_CONFIGURED, OUT_OF_CREDITS, UNAVAILABLE, to_provider_error

REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def _error(cls: type[anthropic.APIStatusError], status: int, kind: str, message: str) -> anthropic.APIStatusError:
    body = {"type": "error", "error": {"type": kind, "message": message}}
    return cls(message, response=httpx2.Response(status, request=REQUEST, json=body), body=body)


@pytest.mark.parametrize(
    ("exc", "message", "retryable"),
    [
        (_error(anthropic.APIStatusError, 402, "billing_error", "Billing problem."), OUT_OF_CREDITS, False),
        (
            _error(
                anthropic.BadRequestError,
                400,
                "invalid_request_error",
                "Your credit balance is too low to access the Anthropic API.",
            ),
            OUT_OF_CREDITS,
            False,
        ),
        (
            _error(anthropic.AuthenticationError, 401, "authentication_error", "invalid x-api-key"),
            NOT_CONFIGURED,
            False,
        ),
        (_error(anthropic.RateLimitError, 429, "rate_limit_error", "Slow down."), BUSY, True),
        (_error(anthropic.OverloadedError, 529, "overloaded_error", "Overloaded."), UNAVAILABLE, True),
        (anthropic.APIConnectionError(request=REQUEST), UNAVAILABLE, True),
    ],
)
def test_sdk_errors_become_messages_a_person_can_act_on(exc, message, retryable):
    err = to_provider_error(exc)
    assert err.user_message == message and err.retryable is retryable
