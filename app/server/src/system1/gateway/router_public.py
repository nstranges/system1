import logging
import time
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from system1.config import get_settings
from system1.contracts.decisions import ChoiceAnswer, ProviderError
from system1.db import get_session
from system1.decisions import service as feedback_service
from system1.decisions.models import Decision
from system1.errors import ApiError, NotFound, Unauthenticated
from system1.gateway import service
from system1.gateway.keys import ApiKey, resolve_key
from system1.gateway.service import Lane, LaneResult, State
from system1.projects.models import Project
from system1.providers import Providers, get_providers

# Authenticates with a project API key only. Clerk sessions are not accepted here.
router = APIRouter(prefix="/v1")

log = logging.getLogger(__name__)

SessionDep = Annotated[Session, Depends(get_session)]
ProvidersDep = Annotated[Providers, Depends(get_providers)]

SYS1_MISSING = "Your model isn't connected yet."


class BadModel(ApiError):
    status_code = 422
    code = "invalid_model"
    message = "Unknown model. Use jev-1.13.0, sys1 or auto."


class DecideIn(BaseModel):
    # Any project-like field is ignored: the key decides the project.
    model: str | None = None
    state: State
    # Accepted for Jev compatibility. The project's rules define the question.
    questions: dict | None = None


class Sys1Block(BaseModel):
    decision_id: str
    routed_to: str
    policy_version: int
    latency_ms: float


class DecideOut(BaseModel):
    model: str
    answers: dict[str, ChoiceAnswer]
    usage: dict | None = None
    system1: Sys1Block


class FeedbackIn(BaseModel):
    decision_id: str
    correct: dict[str, str]


class FeedbackOut(BaseModel):
    status: str = "recorded"


def key_from_bearer(session: SessionDep, authorization: Annotated[str | None, Header()] = None) -> ApiKey:
    scheme, _, raw = (authorization or "").partition(" ")
    key = resolve_key(session, raw.strip()) if scheme.lower() == "bearer" and raw.strip() else None
    if key is None:
        raise Unauthenticated("Send a valid project API key as a Bearer token.")
    return key


KeyDep = Annotated[ApiKey, Depends(key_from_bearer)]


def _lane_for(model: str | None, project: Project) -> str:
    wanted = (model or project.default_lane).lower()
    if wanted in {"jev", "jev-latest", get_settings().jev_model.lower()}:
        return "jev"
    if wanted in {"sys1", "auto"}:
        return wanted
    raise BadModel()


async def _run(
    session: Session, providers: Providers, project: Project, state: State, lane: Lane, policy_and_version
) -> LaneResult:
    result = await service.run_lane(
        session, providers, project, state, lane, "api", policy_and_version=policy_and_version
    )
    if result.error:
        raise ProviderError(result.error, retryable=result.retryable)
    return result


@router.post("/systemone")
async def decide(body: DecideIn, key: KeyDep, session: SessionDep, providers: ProvidersDep) -> DecideOut:
    started = time.perf_counter()
    project = session.get(Project, key.project_id)
    if project is None:
        raise Unauthenticated()
    wanted = _lane_for(body.model, project)
    policy_and_version = service.latest_policy(session, project)
    service.check_length(body.state)

    flag_review = False
    if wanted == "sys1":
        if providers.sys1 is None:
            raise ProviderError(SYS1_MISSING, retryable=True)
        result = await _run(session, providers, project, body.state, "sys1", policy_and_version)
    elif wanted == "auto" and providers.sys1 is not None:
        result = await service.run_lane(
            session, providers, project, body.state, "sys1", "api", policy_and_version=policy_and_version
        )
        # Judge by `probabilities`: Jev and Laya define `confidence` differently.
        sure = result.error is None and max(result.probabilities.values(), default=0.0) >= get_settings().auto_threshold
        if not sure:
            flag_review = result.error is None
            if result.error:
                log.warning("sys1 failed, falling back to jev for project %s: %s", project.id, result.error)
            result = await _run(session, providers, project, body.state, "jev", policy_and_version)
    else:
        result = await _run(session, providers, project, body.state, "jev", policy_and_version)

    decision = session.get(Decision, result.decision_id)
    if decision is None:
        raise NotFound("Decision not found.")
    if flag_review:
        decision.needs_review = True
        session.commit()
    return DecideOut(
        model=decision.model_reported,
        answers={k: ChoiceAnswer(**v) for k, v in decision.answers_json.items()},
        system1=Sys1Block(
            decision_id=decision.id,
            routed_to=decision.model_reported,
            policy_version=decision.policy_version,
            latency_ms=(time.perf_counter() - started) * 1000,
        ),
    )


@router.post("/feedback")
def feedback(body: FeedbackIn, key: KeyDep, session: SessionDep) -> FeedbackOut:
    decision = session.get(Decision, body.decision_id)
    if decision is None or decision.project_id != key.project_id:
        raise NotFound("Decision not found.")
    project = session.get(Project, key.project_id)
    if project is None:
        raise Unauthenticated()
    question_key = feedback_service.question_key(session, project)
    label = body.correct.get(question_key)
    if label is None:
        raise feedback_service.BadLabel(f"Send the right answer as correct.{question_key}.")
    feedback_service.record_feedback(session, None, decision, "api_correction", label)
    return FeedbackOut()
