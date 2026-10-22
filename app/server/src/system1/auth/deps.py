from fastapi import Request

from system1.auth.principal import Principal, principal_from_claims
from system1.errors import Unauthenticated


def get_principal(request: Request) -> Principal:
    # Sync on purpose: the Clerk SDK call may block, and FastAPI runs sync deps in a threadpool.
    claims = request.app.state.verifier.claims(request)
    if claims is None:
        raise Unauthenticated()
    return principal_from_claims(claims)
