from collections.abc import AsyncIterator

import anthropic
from sqlalchemy import func, select

from system1.agent.context import AgentContext
from system1.agent.events import (
    AgentEvent,
    CanvasEvent,
    DoneEvent,
    ErrorEvent,
    StageEvent,
    TextEvent,
    UserEvent,
)
from system1.agent.models import AgentTurn
from system1.agent.prompts import canvas_message, system_blocks
from system1.agent.tools import execute_tool, tool_definitions
from system1.contracts.decisions import ProviderError
from system1.contracts.llm import TextDelta, TurnComplete
from system1.errors import NotFound
from system1.projects.service import latest_policy
from system1.usage import BudgetExceeded, check_budget, record_usage

MAX_TOOL_ROUNDS = 8


def _append(ctx: AgentContext, role: str, content: str | list, ui: list[AgentEvent] | None = None) -> None:
    ctx.session.flush()
    seq = (ctx.session.scalar(select(func.max(AgentTurn.seq)).where(AgentTurn.project_id == ctx.project.id)) or 0) + 1
    ctx.session.add(
        AgentTurn(
            project_id=ctx.project.id,
            org_id=ctx.principal.org_id,
            seq=seq,
            role=role,
            api_content_json=content,
            ui_events_json=[e.model_dump(mode="json") for e in ui or []],
        )
    )
    ctx.session.commit()


def load_messages(ctx: AgentContext) -> list[dict]:
    turns = ctx.session.scalars(select(AgentTurn).where(AgentTurn.project_id == ctx.project.id).order_by(AgentTurn.seq))
    return [{"role": t.role, "content": t.api_content_json} for t in turns]


def _canvas_turn(ctx: AgentContext) -> None:
    try:
        policy, version = latest_policy(ctx.session, ctx.project)
    except NotFound:
        policy, version = None, None
    message = canvas_message(policy, version, ctx.project.stage)
    _append(ctx, "system", message["content"])


async def _run(ctx: AgentContext, user_text: str) -> AsyncIterator[AgentEvent]:
    check_budget(ctx.session, ctx.principal.org_id)

    _append(ctx, "user", user_text, [UserEvent(text=user_text)])
    _canvas_turn(ctx)
    tools = tool_definitions()
    system = system_blocks(ctx.settings)

    for _ in range(MAX_TOOL_ROUNDS):
        complete: TurnComplete | None = None
        async for item in ctx.providers.llm.stream_turn(system=system, messages=load_messages(ctx), tools=tools):
            if isinstance(item, TextDelta):
                yield TextEvent(delta=item.text)
            elif isinstance(item, TurnComplete):
                complete = item
        if complete is None:
            raise ProviderError("The AI assistant returned no answer. Try again.", retryable=True)

        record_usage(ctx.session, ctx.principal.org_id, complete.input_tokens + complete.output_tokens)
        text = "".join(b.get("text", "") for b in complete.content if b.get("type") == "text")
        tool_uses = [b for b in complete.content if b.get("type") == "tool_use"]
        # Tools run to completion before anything more is yielded, so a dropped connection can't leave a
        # tool_use in the history without its result.
        results: list[dict] = []
        events: list[AgentEvent] = []
        for use in tool_uses:
            output, tool_events = await execute_tool(use["name"], use.get("input") or {}, ctx)
            events.extend(tool_events)
            block = {"type": "tool_result", "tool_use_id": use["id"], "content": output}
            if output.startswith("Error:"):
                block["is_error"] = True
            results.append(block)

        _append(ctx, "assistant", complete.content, [TextEvent(delta=text)] if text else [])
        if not tool_uses:
            return
        _append(ctx, "user", results, events)
        for event in events:
            yield event
        if any(isinstance(e, CanvasEvent | StageEvent) for e in events):
            _canvas_turn(ctx)


async def run_agent_turn(ctx: AgentContext, user_text: str) -> AsyncIterator[AgentEvent]:
    try:
        async for event in _run(ctx, user_text):
            yield event
    except BudgetExceeded as exc:
        yield ErrorEvent(message=exc.message)
    except ProviderError as exc:
        yield ErrorEvent(message=exc.user_message)
    except anthropic.APIError:
        yield ErrorEvent(message="The AI assistant had a problem. Try again in a moment.")
    yield DoneEvent()
