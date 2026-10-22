from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from system1.contracts.decisions import ProviderError
from system1.domain.policy import PolicyIssue


class ApiError(Exception):
    """An error the client can act on. Every API error serializes as {"detail": {"code", "message"}}."""

    status_code = 500
    code = "internal_error"
    message = "Something went wrong."

    def __init__(self, message: str | None = None):
        self.message = message or self.message
        super().__init__(self.message)


class Unauthenticated(ApiError):
    status_code = 401
    code = "unauthenticated"
    message = "Sign in to continue."


class NotFound(ApiError):
    status_code = 404
    code = "not_found"
    message = "Not found."


class PolicyInvalid(ApiError):
    status_code = 422
    code = "policy_invalid"
    message = "This policy has problems that need fixing before it can be saved."

    def __init__(self, issues: list[PolicyIssue]):
        super().__init__()
        self.issues = issues


class InputTooLong(ApiError):
    status_code = 422
    code = "input_too_long"

    def __init__(self, length: int, limit: int):
        super().__init__(f"This input is {length} characters. The limit is {limit}.")


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _handle(_: Request, exc: ApiError) -> JSONResponse:
        detail: dict = {"code": exc.code, "message": exc.message}
        if isinstance(exc, PolicyInvalid):
            detail["issues"] = [issue.model_dump() for issue in exc.issues]
        return JSONResponse(status_code=exc.status_code, content={"detail": detail})

    @app.exception_handler(ProviderError)
    async def _handle_provider(_: Request, exc: ProviderError) -> JSONResponse:
        return JSONResponse(
            status_code=503 if exc.retryable else 502,
            content={"detail": {"code": "provider_error", "message": exc.user_message}},
        )
