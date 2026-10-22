from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from system1.auth.deps import get_principal
from system1.auth.principal import Principal
from system1.db import get_session
from system1.domain.policy import Policy, PolicyIssue, validate_policy
from system1.drafting import service
from system1.projects.service import get_project
from system1.providers import Providers, get_providers
from system1.usage import check_budget, record_usage

router = APIRouter(prefix="/projects", dependencies=[Depends(get_principal)])

PrincipalDep = Annotated[Principal, Depends(get_principal)]
SessionDep = Annotated[Session, Depends(get_session)]
ProvidersDep = Annotated[Providers, Depends(get_providers)]


class DraftIn(BaseModel):
    source: Literal["examples", "context"]


class DraftOut(BaseModel):
    policy: Policy
    notes: list[str]
    # Shown next to the draft: applying it goes through PUT /policy, which rejects an invalid policy.
    issues: list[PolicyIssue]


@router.post("/{project_id}/draft")
async def draft(
    project_id: str, body: DraftIn, principal: PrincipalDep, session: SessionDep, providers: ProvidersDep
) -> DraftOut:
    project = get_project(session, principal, project_id)
    check_budget(session, principal.org_id)
    make = service.draft_from_examples if body.source == "examples" else service.draft_from_context
    result = await make(session, providers.llm, project)
    record_usage(session, principal.org_id, result.tokens)
    return DraftOut(policy=result.policy, notes=result.notes, issues=validate_policy(result.policy))
