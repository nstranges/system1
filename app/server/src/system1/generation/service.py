import math

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from system1.agent.context import AgentContext, register_action_handler
from system1.agent.models import PendingAction
from system1.auth.principal import Principal
from system1.config import Settings
from system1.context.service import context_text
from system1.contracts.generation import GeneratedExample
from system1.datasets import service as dataset_service
from system1.datasets.constants import DEFAULT_TARGET, GENERATION_CAP
from system1.datasets.models import Example
from system1.datasets.service import NewExample, UnknownBucket
from system1.domain.policy import Policy, validate_policy
from system1.errors import ApiError
from system1.jobs import service as job_service
from system1.jobs.service import JobContext
from system1.projects import service as project_service
from system1.projects.models import Project
from system1.providers import Providers
from system1.usage import check_budget, record_usage

# Uploaded rows show the writer what real inputs look like; a few are enough and keep the prompt small.
STYLE_SAMPLES = 5
STYLE_SAMPLE_CHARS = 500
EXAMPLES_PER_MINUTE = 50


class BucketsUnfinished(ApiError):
    status_code = 422
    code = "buckets_unfinished"
    message = "Finish your buckets before generating examples."


class TooManyToGenerate(ApiError):
    status_code = 422
    code = "generation_cap"
    message = f"Generate up to {GENERATION_CAP} examples at a time."


class NothingToGenerate(ApiError):
    status_code = 422
    code = "nothing_to_generate"
    message = "Every bucket already has enough examples."


class Estimate(BaseModel):
    examples: int
    est_minutes: int
    est_cost_usd: float


def estimate(settings: Settings, targets: dict[str, int]) -> Estimate:
    examples = sum(targets.values())
    return Estimate(
        examples=examples,
        est_minutes=max(1, math.ceil(examples / EXAMPLES_PER_MINUTE)),
        est_cost_usd=round(examples * settings.est_cost_per_example_usd, 2),
    )


def resolve_targets(
    session: Session, project: Project, targets: dict[str, int] | None
) -> tuple[Policy, dict[str, int]]:
    """The policy to write for and how many examples each bucket gets, checked. Callers must have checked org access."""
    policy, _ = project_service.latest_policy(session, project)
    if validate_policy(policy):
        raise BucketsUnfinished()
    keys = {o.key for o in policy.options}
    if targets is None:
        per_bucket = dataset_service.health(session, project).per_bucket
        targets = {k: max(0, DEFAULT_TARGET - per_bucket[k]["total"]) for k in keys}
    else:
        unknown = sorted(set(targets) - keys)
        if unknown:
            raise UnknownBucket(f"These aren't buckets in this project: {', '.join(unknown[:5])}.")
        if any(n < 0 for n in targets.values()):
            raise UnknownBucket("Example counts can't be negative.")
    targets = {k: n for k, n in targets.items() if n > 0}
    total = sum(targets.values())
    if total > GENERATION_CAP:
        raise TooManyToGenerate()
    if total == 0:
        raise NothingToGenerate()
    return policy, targets


def _style_samples(session: Session, project: Project, policy: Policy) -> list[str]:
    uploaded = session.scalars(
        select(Example.input_json)
        .where(Example.project_id == project.id, Example.source == "uploaded")
        .order_by(Example.created_at, Example.id)
        .limit(STYLE_SAMPLES)
    )
    return [*policy.sample_inputs, *(v[:STYLE_SAMPLE_CHARS] for v in uploaded if isinstance(v, str))]


def start_generation(
    session: Session,
    providers: Providers,
    settings: Settings,
    principal: Principal,
    project: Project,
    targets: dict[str, int] | None,
) -> str:
    """Starts the job and returns its id. Call it from the event loop thread (an async route or handler)."""
    project_service.get_project(session, principal, project.id)
    policy, wanted = resolve_targets(session, project, targets)
    check_budget(session, principal.org_id)
    context = context_text(session, project)
    samples = _style_samples(session, project, policy)
    job = job_service.create_job(session, principal, project.id, "generation")
    org_id, project_id, requested = principal.org_id, project.id, sum(wanted.values())

    async def work(ctx: JobContext) -> dict:
        own_project = ctx.session.get(Project, project_id)
        added = 0
        ctx.result = {"added": 0, "requested": requested}

        def before_batch() -> None:
            check_budget(ctx.session, org_id)

        def on_batch(batch: list[GeneratedExample], tokens: int) -> None:
            nonlocal added
            rows = [NewExample(g.input, g.label, "generated", g.how_sure) for g in batch]
            added += dataset_service.add_examples(ctx.session, own_project, rows)
            record_usage(ctx.session, org_id, tokens)
            ctx.result = {"added": added, "requested": requested}

        await providers.generator.generate(
            policy,
            context,
            samples,
            wanted,
            lambda p: ctx.progress(p, "writing"),
            before_batch=before_batch,
            on_batch=on_batch,
        )
        return {"added": added, "requested": requested}

    job_service.start_job(job_service.session_factory_for(session), job.id, work)
    return job.id


async def _confirm_generation(ctx: AgentContext, action: PendingAction) -> dict:
    job_id = start_generation(
        ctx.session, ctx.providers, ctx.settings, ctx.principal, ctx.project, action.params_json.get("targets")
    )
    return {"job_id": job_id}


# "dataset" is the kind older confirmation cards were saved with.
register_action_handler("generation", _confirm_generation)
register_action_handler("dataset", _confirm_generation)
