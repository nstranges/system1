from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


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


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _handle(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": {"code": exc.code, "message": exc.message}},
        )
