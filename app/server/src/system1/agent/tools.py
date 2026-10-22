import math
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from system1.agent.context import AgentContext
from system1.agent.events import (
    AgentEvent,
    CanvasEvent,
    ChoicesEvent,
    ConfirmEvent,
    FitEvent,
    StageEvent,
    ToolEvent,
    TryResultEvent,
)
from system1.agent.models import PendingAction
from system1.domain.policy import InputField, Option, Policy, Rule, validate_policy
from system1.errors import ApiError, NotFound
from system1.gateway.service import try_input
from system1.projects.service import latest_policy, save_policy
from system1.templates.catalog import load_templates

STAGES = ("usecase", "rules", "try", "examples", "train", "use", "improve")
MAX_DATASET_EXAMPLES = 50
TRAINING_ESTIMATE_MINUTES = 15.0


class ShowChoices(BaseModel):
    """Ask the user one question with 2 to 4 buttons to pick from."""

    question: str
    options: list[str]


class ShowFit(BaseModel):
    """Tell the user how well their decision suits this tool."""

    rating: Literal["good", "workable", "poor"]
    reasons: list[str]


class SearchUseCases(BaseModel):
    """Search the gallery of ready-made use cases."""

    query: str


class SetInputs(BaseModel):
    """Replace the list of facts the decision looks at."""

    inputs: list[InputField]


class SetOptions(BaseModel):
    """Replace the list of possible outcomes. Option keys are snake_case."""

    options: list[Option]
    decision_question: str | None = Field(
        default=None, description="The question the decision answers, if changing it."
    )


class SetRules(BaseModel):
    """Replace the routing rules. Every rule's label must be an option key and every field an input key."""

    rules: list[Rule]


class TryDecision(BaseModel):
    """Run one example through the decision so the user can see the result."""

    input: str


class RequestDataset(BaseModel):
    """Ask the user to confirm generating practice examples. This only shows a confirmation card."""

    count: int = Field(ge=1, le=MAX_DATASET_EXAMPLES)


class RequestTraining(BaseModel):
    """Ask the user to confirm training their own model. This only shows a confirmation card."""


class GoToStage(BaseModel):
    """Move the workspace to another stage."""

    stage: Literal["usecase", "rules", "try", "examples", "train", "use", "improve"]


_TOOLS: dict[str, type[BaseModel]] = {
    "show_choices": ShowChoices,
    "show_fit": ShowFit,
    "search_use_cases": SearchUseCases,
    "set_inputs": SetInputs,
    "set_options": SetOptions,
    "set_rules": SetRules,
    "try_decision": TryDecision,
    "request_dataset": RequestDataset,
    "request_training": RequestTraining,
    "go_to_stage": GoToStage,
}


def _schema(model: type[BaseModel]) -> dict:
    schema = model.model_json_schema()
    schema.pop("title", None)
    schema.pop("description", None)
    schema["additionalProperties"] = False
    return schema


def tool_definitions() -> list[dict]:
    return [
        {
            "name": name,
            "description": (model.__doc__ or "").strip(),
            "input_schema": _schema(model),
            # Stream tool arguments as they are generated instead of waiting for the full JSON.
            "eager_input_streaming": True,
        }
        for name, model in _TOOLS.items()
    ]


def _blank_policy() -> Policy:
    return Policy(decision_question="", options=[])


def _policy(ctx: AgentContext) -> tuple[Policy, int | None]:
    try:
        return latest_policy(ctx.session, ctx.project)
    except NotFound:
        return _blank_policy(), None


def _save(ctx: AgentContext, policy: Policy, changed: list[str]) -> tuple[str, list[AgentEvent]]:
    issues = validate_policy(policy)
    if issues:
        listing = "\n".join(f"- {i.path}: {i.message}" for i in issues)
        raise ToolError(f"The policy was not changed. Fix these problems and try again:\n{listing}")
    version = save_policy(ctx.session, ctx.principal, ctx.project, policy)
    return f"Saved as version {version}.", [CanvasEvent(policy=policy, version=version, changed=changed)]


class ToolError(Exception):
    """A problem the model can read and recover from. Shown to it as an error tool result."""


async def _run(name: str, args: BaseModel, ctx: AgentContext) -> tuple[str, list[AgentEvent]]:
    if isinstance(args, ShowChoices):
        if not 2 <= len(args.options) <= 4:
            raise ToolError("show_choices needs 2 to 4 options.")
        return "Shown to the user. Wait for their answer.", [ChoicesEvent(question=args.question, options=args.options)]
    if isinstance(args, ShowFit):
        return "Shown to the user.", [FitEvent(rating=args.rating, reasons=args.reasons)]
    if isinstance(args, SearchUseCases):
        words = args.query.lower().split()
        found = [
            t for t in load_templates() if any(w in f"{t.name} {t.summary}".lower() for w in words)
        ] or load_templates()
        return "\n".join(f"- {t.id}: {t.name} (fit: {t.fit}). {t.summary}" for t in found), []
    if isinstance(args, SetInputs):
        policy, _ = _policy(ctx)
        return _save(ctx, policy.model_copy(update={"inputs": args.inputs}), ["inputs"])
    if isinstance(args, SetOptions):
        policy, _ = _policy(ctx)
        update: dict = {"options": args.options}
        if args.decision_question is not None:
            update["decision_question"] = args.decision_question
        return _save(ctx, policy.model_copy(update=update), ["options"])
    if isinstance(args, SetRules):
        policy, _ = _policy(ctx)
        return _save(ctx, policy.model_copy(update={"rules": args.rules}), ["rules"])
    if isinstance(args, TryDecision):
        result = await try_input(ctx.session, ctx.providers, ctx.project, args.input)
        lines = [f"- {r.lane}: {r.label or r.error}" for r in result.results]
        return "Results:\n" + "\n".join(lines), [TryResultEvent(input=args.input, result=result)]
    if isinstance(args, RequestDataset):
        minutes = max(1.0, math.ceil(args.count / 10))
        cost = args.count * ctx.settings.est_cost_per_example_usd
        action = _pending(ctx, "dataset", {"count": args.count})
        event = ConfirmEvent(
            action_id=action.id,
            kind="dataset",
            title=f"Generate {args.count} practice examples",
            detail="Examples are written by an AI from your rules, so you can check them before training.",
            est_minutes=minutes,
            est_cost_usd=cost,
        )
        return "A confirmation card was shown. Nothing has started. Wait for the user.", [event]
    if isinstance(args, RequestTraining):
        action = _pending(ctx, "training", {})
        event = ConfirmEvent(
            action_id=action.id,
            kind="training",
            title="Train your own model",
            detail="Trains a small model on your examples and checks it against held-out ones.",
            est_minutes=TRAINING_ESTIMATE_MINUTES,
            est_cost_usd=0.0,
        )
        return "A confirmation card was shown. Nothing has started. Wait for the user.", [event]
    if isinstance(args, GoToStage):
        ctx.project.stage = args.stage
        ctx.session.commit()
        return f"Moved to {args.stage}.", [StageEvent(stage=args.stage)]
    raise ToolError(f"Unknown tool {name}.")


def _pending(ctx: AgentContext, kind: str, params: dict) -> PendingAction:
    action = PendingAction(project_id=ctx.project.id, org_id=ctx.principal.org_id, kind=kind, params_json=params)
    ctx.session.add(action)
    ctx.session.commit()
    return action


async def execute_tool(name: str, args: dict, ctx: AgentContext) -> tuple[str, list[AgentEvent]]:
    """Returns (result text for the model, events for the UI). A failure comes back as text prefixed
    "Error:" with an error tool event, never as an exception, so the model can recover."""
    started = ToolEvent(name=name, status="started")
    model = _TOOLS.get(name)
    if model is None:
        return f"Error: unknown tool {name}.", [ToolEvent(name=name, status="error", summary="Unknown tool.")]
    try:
        parsed = model.model_validate(args)
        text, events = await _run(name, parsed, ctx)
    except ValidationError as exc:
        problems = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
        return f"Error: invalid arguments. {problems}", [
            started,
            ToolEvent(name=name, status="error", summary=problems),
        ]
    except (ToolError, ApiError) as exc:
        return f"Error: {exc}", [started, ToolEvent(name=name, status="error", summary=str(exc).split("\n")[0])]
    return text, [started, *events, ToolEvent(name=name, status="done", summary=text.split("\n")[0])]
