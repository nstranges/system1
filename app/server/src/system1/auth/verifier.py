import logging
from typing import Protocol

import httpx
from clerk_backend_api import Clerk
from clerk_backend_api.security.types import AuthenticateRequestOptions
from fastapi import Request

log = logging.getLogger(__name__)


class TokenVerifier(Protocol):
    def claims(self, request: Request) -> dict | None: ...


class ClerkVerifier:
    def __init__(self, secret_key: str, authorized_parties: list[str]):
        self._clerk = Clerk(bearer_auth=secret_key)
        self._authorized_parties = authorized_parties

    def claims(self, request: Request) -> dict | None:
        # The SDK only reads headers, but wants an httpx request. It does a blocking JWKS fetch
        # on a cold cache, so callers must be sync (FastAPI runs them in its threadpool).
        adapted = httpx.Request(request.method, str(request.url), headers=request.headers.raw)
        state = self._clerk.authenticate_request(
            adapted, AuthenticateRequestOptions(authorized_parties=self._authorized_parties)
        )
        if not state.is_signed_in:
            log.info("rejected session token: %s", state.reason)
            return None
        return state.payload


class FakeVerifier:
    def __init__(self, claims: dict | None):
        self._claims = claims

    def claims(self, request: Request) -> dict | None:
        return self._claims


class RejectAllVerifier:
    def claims(self, request: Request) -> dict | None:
        return None
