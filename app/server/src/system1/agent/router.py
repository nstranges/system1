import logging
from collections.abc import AsyncIterator
from contextlib import aclosing
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, TypeAdapter, ValidationError
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from system1.agent.context import AgentContext, get_action_handler
from system1.agent.events import AgentEvent
from system1.agent.loop import clear_thread, run_agent_turn
from system1.agent.models import AgentTurn, PendingAction
from system1.auth.deps import get_principal
from system1.auth.principal import Principal
from system1.config import Settings, get_settings
from system1.db import get_session
from system1.errors import ApiError, NotFound
from system1.projects.service import get_project
from system1.providers import Providers, get_providers

log = logging.getLogger(__name__)

router = APIRouter(prefix="/projects", dependencies=[Depends(get_principal)])

PrincipalDep = Annotated[Principal, Depends(get_principal)]
SessionDep = Annotated[Session, Depends(get_session)]
ProvidersDep = Annotated[Providers, Depends(get_providers)]

_event_adapter: TypeAdapter[AgentEvent] = TypeAdapter(AgentEvent)


class NotAvailable(ApiError):
    status_code = 409
    code = "not_available"
    message = "Not available yet."


class AlreadyResolved(ApiError):
    status_code = 409
    code = "already_resolved"
    message = "This was already confirmed or cancelled."


class MessageIn(BaseModel):
    text: str
    # The step the person is looking at. A value that isn't one of the six steps is ignored.
    stage: str | None = None


class ConfirmOut(BaseModel):
    status: str
    result: dict


def _sse(event: AgentEvent) -> str:
    return f"event: {event.type}\ndata: {event.model_dump_json()}\n\n"


@router.post("/{project_id}/agent/messages", response_class=StreamingResponse)
async def send_message(
    project_id: str,
    body: MessageIn,
    request: Request,
    principal: PrincipalDep,
    session: SessionDep,
    providers: ProvidersDep,
) -> StreamingResponse:
    get_project(session, principal, project_id)  # 404 before the stream starts

    async def stream() -> AsyncIterator[str]:
        # The stream outlives the request's dependency session, so it opens its own.
        with Session(request.app.state.engine) as own:
            ctx = AgentContext(own, principal, providers, get_settings(), get_project(own, principal, project_id))
            # aclosing so a client disconnect finalises the turn (history repair) while this session is open.
            async with aclosing(run_agent_turn(ctx, body.text, body.stage)) as events:
                async for event in events:
                    yield _sse(event)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@router.get("/{project_id}/agent/history")
def history(project_id: str, principal: PrincipalDep, session: SessionDep) -> list[AgentEvent]:
    project = get_project(session, principal, project_id)
    turns = session.scalars(select(AgentTurn).where(AgentTurn.project_id == project.id).order_by(AgentTurn.seq))
    events: list[AgentEvent] = []
    for turn in turns:
        for raw in turn.ui_events_json:
            try:
                events.append(_event_adapter.validate_python(raw))
            except ValidationError:
                # Saved by an older version of the app; one unreadable event shouldn't hide the whole thread.
                log.warning("skipping unreadable agent event %r in project %s", raw.get("type"), project.id)
    return events


@router.delete("/{project_id}/agent/history", status_code=204)
def start_over(project_id: str, principal: PrincipalDep, session: SessionDep, providers: ProvidersDep) -> Response:
    project = get_project(session, principal, project_id)
    clear_thread(AgentContext(session, principal, providers, get_settings(), project))
    return Response(status_code=204)


def _action(session: Session, principal: Principal, project_id: str, action_id: str) -> PendingAction:
    project = get_project(session, principal, project_id)
    action = session.get(PendingAction, action_id)
    if action is None or action.project_id != project.id or action.org_id != principal.org_id:
        raise NotFound("Action not found.")
    return action


@router.post("/{project_id}/actions/{action_id}/confirm")
async def confirm(
    project_id: str, action_id: str, principal: PrincipalDep, session: SessionDep, providers: ProvidersDep
) -> ConfirmOut:
    action = _action(session, principal, project_id, action_id)
    if action.status != "pending":
        raise AlreadyResolved()
    handler = get_action_handler(action.kind)
    if handler is None:
        raise NotAvailable()
    project = get_project(session, principal, project_id)
    # Claim atomically so two concurrent confirms can't both start paid work.
    claimed = session.execute(
        update(PendingAction)
        .where(PendingAction.id == action.id, PendingAction.status == "pending")
        .values(status="confirmed")
    )
    session.commit()
    if claimed.rowcount == 0:
        raise AlreadyResolved()
    settings: Settings = get_settings()
    try:
        result = await handler(AgentContext(session, principal, providers, settings, project), action)
    except Exception:
        # Nothing ran, so let the user try again.
        session.rollback()
        session.execute(update(PendingAction).where(PendingAction.id == action.id).values(status="pending"))
        session.commit()
        raise
    return ConfirmOut(status="confirmed", result=result)


@router.post("/{project_id}/actions/{action_id}/cancel")
def cancel(project_id: str, action_id: str, principal: PrincipalDep, session: SessionDep) -> ConfirmOut:
    action = _action(session, principal, project_id, action_id)
    if action.status != "pending":
        raise AlreadyResolved()
    action.status = "cancelled"
    session.commit()
    return ConfirmOut(status="cancelled", result={})
