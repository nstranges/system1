from dataclasses import dataclass

from system1.errors import ApiError


class NoActiveOrganization(ApiError):
    status_code = 403
    code = "no_active_org"
    message = "Select or create an organization to continue."


@dataclass(frozen=True)
class Principal:
    user_id: str
    org_id: str
    org_role: str
    org_slug: str | None


def principal_from_claims(claims: dict) -> Principal:
    """Read a Clerk session token v2. `rol` arrives without the `org:` prefix."""
    org = claims.get("o")
    if claims.get("sts") == "pending" or not org or not org.get("id"):
        raise NoActiveOrganization()
    return Principal(user_id=claims["sub"], org_id=org["id"], org_role=org.get("rol", ""), org_slug=org.get("slg"))
