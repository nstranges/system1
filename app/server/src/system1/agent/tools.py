import re
from typing import Annotated, Literal

from pydantic import BaseModel, Field, ValidationError

from system1.agent.context import AgentContext
from system1.agent.events import (
    AgentEvent,
    CanvasEvent,
    CanvasProposalEvent,
    ChoicesEvent,
    ConfirmEvent,
    FitEvent,
    StageEvent,
    ToolEvent,
    TryResultEvent,
)
from system1.agent.models import PendingAction
from system1.datasets.constants import GENERATION_CAP, MAX_GUIDELINE_CHARS, MAX_GUIDELINES
from system1.domain.policy import Option, Policy, validate_policy
from system1.drafting import service as drafting
from system1.errors import ApiError, NotFound
from system1.gateway.service import try_input
from system1.generation import service as generation
from system1.projects.service import latest_policy, save_policy
from system1.templates.catalog import load_templates
from system1.usage import check_budget, record_usage

STAGES = ("define", "data", "review", "train", "use", "improve")
# Projects made before the six steps were stored a stage under the old names.
LEGACY_STAGES = {"usecase": "define", "rules": "define", "examples": "data", "try": "use"}


def step_name(stage: str) -> str | None:
    """The current name of a stored stage, or None when it isn't one the assistant knows."""
    stage = LEGACY_STAGES.get(stage, stage)
    return stage if stage in STAGES else None


def tool_names() -> set[str]:
    return set(_TOOLS)


Stage = Literal["define", "data", "review", "train", "use", "improve"]
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


class BucketIn(BaseModel):
    key: str = Field(max_length=drafting.MAX_KEY_CHARS, description="Short snake_case name, for example billing.")
    name: str = Field(max_length=drafting.MAX_NAME_CHARS)
    use_when: list[Annotated[str, Field(max_length=drafting.MAX_LINE_CHARS)]] = Field(
        default_factory=list, max_length=drafting.MAX_USE_WHEN, description="Short 'use this when...' lines."
    )
    example: str | None = Field(default=None, description="One sample input that belongs here.")


class SetBuckets(BaseModel):
    """Replace the whole list of buckets (the possible answers). Send every bucket you want to keep, in order. A bucket that has examples can't be removed."""

    buckets: list[BucketIn]
    decision_question: str | None = Field(
        default=None, description="The question the decision answers, if changing it."
    )


class SetGuidelines(BaseModel):
    """Replace the whole list of guidelines: plain sentences that say how to decide. Send every guideline you want to keep."""

    guidelines: list[Annotated[str, Field(max_length=MAX_GUIDELINE_CHARS)]] = Field(max_length=MAX_GUIDELINES)


class DraftFromExamples(BaseModel):
    """Draft buckets and guidelines from the examples the person added. This only shows a proposal they can apply; nothing is saved."""


class DraftFromContext(BaseModel):
    """Draft buckets and guidelines from the context files the person added. This only shows a proposal they can apply; nothing is saved."""


class QuickCheck(BaseModel):
    """Run one input through Jev, a general model, as a sanity test of the buckets and guidelines. It does not test the person's own model."""

    input: str


class RequestGeneration(BaseModel):
    """Ask the person to confirm writing practice examples. This only shows a confirmation card. Give per-bucket targets or a total count; with neither, every bucket is filled up to the default."""

    targets: dict[str, int] | None = Field(default=None, description="Examples to write per bucket key.")
    count: int | None = Field(default=None, ge=1, le=GENERATION_CAP, description="A total, spread over the buckets.")


class RequestTraining(BaseModel):
    """Ask the user to confirm training their own model. This only shows a confirmation card."""


class GoToStage(BaseModel):
    """Move the workspace to another stage."""

    stage: Stage


_TOOLS: dict[str, type[BaseModel]] = {
    "show_choices": ShowChoices,
    "show_fit": ShowFit,
    "search_use_cases": SearchUseCases,
    "set_buckets": SetBuckets,
    "set_guidelines": SetGuidelines,
    "draft_from_examples": DraftFromExamples,
    "draft_from_context": DraftFromContext,
    "quick_check": QuickCheck,
    "request_generation": RequestGeneration,
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


def _plain(text: str) -> str:
    """The checks speak in the code's words; the assistant and the person hear buckets."""
    return re.sub(r"\boptions?\b", lambda m: "buckets" if m.group().endswith("s") else "bucket", text)


def _save(ctx: AgentContext, policy: Policy, changed: list[str]) -> tuple[str, list[AgentEvent]]:
    issues = validate_policy(policy)
    if issues:
        listing = "\n".join(f"- {_plain(i.path)}: {_plain(i.message)}" for i in issues)
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
    if isinstance(args, SetBuckets):
        policy, _ = _policy(ctx)
        before = {o.key: o for o in policy.options}
        options = [
            Option(
                key=b.key,
                name=b.name,
                covers=b.use_when,
                excludes=before[b.key].excludes if b.key in before else [],
                example=b.example if b.example is not None else (before[b.key].example if b.key in before else ""),
            )
            for b in args.buckets
        ]
        update: dict = {"options": options}
        if args.decision_question is not None:
            update["decision_question"] = args.decision_question
        # Conditions that point at a removed bucket would fail the check and nothing else here can fix them.
        # Removing a bucket that has examples is still refused when the policy is saved.
        keys = {o.key for o in options}
        update["rules"] = [r for r in policy.rules if r.label in keys]
        dropped = len(policy.rules) - len(update["rules"])
        text, events = _save(ctx, policy.model_copy(update=update), ["buckets"])
        if dropped:
            text += f" Also removed {dropped} advanced condition(s) that pointed at removed buckets."
        return text, events
    if isinstance(args, SetGuidelines):
        policy, _ = _policy(ctx)
        return _save(ctx, policy.model_copy(update={"guidelines": args.guidelines}), ["guidelines"])
    if isinstance(args, DraftFromExamples | DraftFromContext):
        source = "examples" if isinstance(args, DraftFromExamples) else "context"
        drafting.require_source(ctx.session, ctx.project, source)
        check_budget(ctx.session, ctx.principal.org_id)
        make = drafting.draft_from_examples if source == "examples" else drafting.draft_from_context
        draft = await make(ctx.session, ctx.providers.llm, ctx.project)
        record_usage(ctx.session, ctx.principal.org_id, draft.tokens)
        issues = validate_policy(draft.policy)
        event = CanvasProposalEvent(policy=draft.policy, notes=draft.notes, issues=issues)
        text = (
            f"Shown to the user as a proposal with {len(draft.policy.options)} buckets and "
            f"{len(draft.policy.guidelines)} guidelines. Nothing is saved until they apply it. "
            "Wait for them, then work from the latest canvas."
        )
        if issues:
            text += " Problems with the draft: " + "; ".join(f"{i.path}: {i.message}" for i in issues)
        return text, [event]
    if isinstance(args, QuickCheck):
        policy, _ = _policy(ctx)
        if validate_policy(policy):
            raise ToolError("Finish the buckets first (at least two) so there is something to check.")
        # Only Jev's two lanes: the person's own model isn't part of a sanity check of the buckets.
        result = await try_input(ctx.session, ctx.providers, ctx.project, args.input, only=("jev_labels", "jev"))
        lines = [f"- {r.lane}: {r.label or r.error}" for r in result.results]
        return "Results (a general model, not the person's own):\n" + "\n".join(lines), [
            TryResultEvent(input=args.input, result=result)
        ]
    if isinstance(args, RequestGeneration):
        if args.targets is not None and args.count is not None:
            raise ToolError("Send either targets or count, not both.")
        targets = args.targets
        if args.count is not None:
            targets = generation.targets_for_count(ctx.session, ctx.project, args.count)
        _, wanted = generation.resolve_targets(ctx.session, ctx.project, targets)
        estimate = generation.estimate(ctx.settings, wanted)
        action = _pending(ctx, "generation", {"targets": wanted})
        event = ConfirmEvent(
            action_id=action.id,
            kind="generation",
            title=f"Write {estimate.examples} practice examples",
            detail="An AI writes them from your buckets and guidelines, and checks how sure it is of each one, so you can review them before training.",
            est_minutes=estimate.est_minutes,
            est_cost_usd=estimate.est_cost_usd,
            examples=estimate.examples,
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
