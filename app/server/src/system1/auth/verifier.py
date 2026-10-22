import base64
import json
import logging
from typing import Protocol

import httpx
from clerk_backend_api import Clerk
from clerk_backend_api.security.types import AuthenticateRequestOptions
from fastapi import Request

log = logging.getLogger(__name__)


def _unverified_azp(request: Request) -> str | None:
    # Diagnostic only: reads one claim from an unverified token and never logs the token itself.
    try:
        token = request.headers.get("authorization", "").removeprefix("Bearer ")
        segment = token.split(".")[1]
        payload = json.loads(base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4)))
        azp = payload.get("azp")
        return azp if isinstance(azp, str) else None
    except (IndexError, ValueError):
        return None


class TokenVerifier(Protocol):
    def claims(self, request: Request) -> dict | None: ...


class ClerkVerifier:
    def __init__(self, secret_key: str, authorized_parties: list[str] | None):
        self._clerk = Clerk(bearer_auth=secret_key)
        self._authorized_parties = authorized_parties

    def options(self) -> AuthenticateRequestOptions:
        # authorized_parties=None skips the azp check (see Settings.clerk_enforce_azp).
        # The SDK default accepts machine, API-key and OAuth tokens too, through a path that skips azp checks.
        return AuthenticateRequestOptions(authorized_parties=self._authorized_parties, accepts_token=["session_token"])

    def claims(self, request: Request) -> dict | None:
        # The SDK only reads headers, but wants an httpx request. It does a blocking JWKS fetch
        # on a cold cache, so callers must be sync (FastAPI runs them in its threadpool).
        adapted = httpx.Request(request.method, str(request.url), headers=request.headers.raw)
        state = self._clerk.authenticate_request(adapted, self.options())
        if not state.is_signed_in:
            reason = state.reason.value[0] if state.reason else "unknown"
            if reason == "token-invalid-authorized-parties":
                log.warning("rejected session token: %s (token azp=%r)", reason, _unverified_azp(request))
            else:
                log.warning("rejected session token: %s", reason)
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
