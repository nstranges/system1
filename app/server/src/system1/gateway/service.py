import asyncio
import json
from typing import Literal

from pydantic import BaseModel
from sqlalchemy.orm import Session

from system1.adapters.eval_files import EvalFilesSource
from system1.adapters.jsonl_dataset import JsonlDatasetSource
from system1.config import get_settings
from system1.contracts.datasets import DatasetRow
from system1.contracts.decisions import DecisionProvider, DecisionRequest, ProviderError
from system1.decisions.models import Decision
from system1.domain.policy import Policy
from system1.domain.questions import build_questions
from system1.errors import InputTooLong, NotFound
from system1.projects.models import Project
from system1.projects.service import latest_policy
from system1.providers import Providers
from system1.templates.catalog import Template, get_template

Lane = Literal["jev", "jev_labels", "sys1"]
State = str | dict | list


class LaneResult(BaseModel):
    lane: Lane
    label: str | None = None
    probabilities: dict[str, float] = {}
    model: str | None = None
    latency_ms: float | None = None
    decision_id: str | None = None
    error: str | None = None
    retryable: bool = False


class TryResult(BaseModel):
    results: list[LaneResult]
    gold: str | None = None
    rule_id: str | None = None
    # Predictions saved from an offline evaluation run, not live calls. The UI labels them "recorded".
    recorded: dict[str, str] = {}
    # True while any recorded prediction comes from sample (fixture) numbers; the UI shows a banner then.
    recorded_is_fixture: bool = False


def _flagship(project: Project) -> Template | None:
    if project.template_id is None:
        return None
    try:
        template = get_template(project.template_id)
    except KeyError:
        return None
    return template if template.flagship else None


def questions_for(project: Project, policy: Policy, lane: Lane) -> dict:
    variant = "policy" if lane == "jev" else "labels"
    template = _flagship(project)
    if template and template.flagship:
        return json.loads(template.flagship.jev_questions_path.read_text())[variant]
    return build_questions(policy, variant)


def flagship_rows(project: Project) -> list[DatasetRow]:
    template = _flagship(project)
    if template is None or template.flagship is None:
        return []
    return JsonlDatasetSource(template.flagship.samples_path).rows("test")


def check_length(state: State) -> None:
    length = len(state) if isinstance(state, str) else len(json.dumps(state))
    limit = get_settings().max_input_chars
    if length > limit:
        raise InputTooLong(length, limit)


def _provider(providers: Providers, lane: Lane) -> DecisionProvider | None:
    return providers.sys1 if lane == "sys1" else providers.jev


async def run_lane(
    session: Session,
    providers: Providers,
    project: Project,
    state: State,
    lane: Lane,
    source: Literal["playground", "api", "agent", "eval"],
    *,
    policy_and_version: tuple[Policy, int] | None = None,
    dataset_row_id: str | None = None,
) -> LaneResult:
    check_length(state)
    provider = _provider(providers, lane)
    if provider is None:
        return LaneResult(lane=lane, error="sys1 isn't connected yet.")
    policy, version = policy_and_version or latest_policy(session, project)
    questions = questions_for(project, policy, lane)
    model = get_settings().jev_model if lane != "sys1" else get_settings().sys1_model
    try:
        response = await provider.decide(DecisionRequest(model=model, state=state, questions=questions))
    except ProviderError as exc:
        return LaneResult(lane=lane, error=exc.user_message, retryable=exc.retryable)

    answer = response.answers.get(next(iter(questions)))
    label = answer.choice if answer else None
    probabilities = answer.probabilities if answer else {}
    decision = Decision(
        org_id=project.org_id,
        project_id=project.id,
        source=source,
        lane=lane,
        model_reported=response.model,
        state_json=state,
        answers_json={k: v.model_dump() for k, v in response.answers.items()},
        top_label=label,
        top_prob=probabilities.get(label) if label else None,
        latency_ms=response.latency_ms,
        policy_version=version,
        not_for_training=lane.startswith("jev"),
        dataset_row_id=dataset_row_id,
    )
    session.add(decision)
    session.commit()
    return LaneResult(
        lane=lane,
        label=label,
        probabilities=probabilities,
        model=response.model,
        latency_ms=response.latency_ms,
        decision_id=decision.id,
    )


async def try_input(
    session: Session,
    providers: Providers,
    project: Project,
    text_or_state: State | None = None,
    sample_id: str | None = None,
) -> TryResult:
    row: DatasetRow | None = None
    if sample_id is not None:
        row = next((r for r in flagship_rows(project) if r.id == sample_id), None)
        if row is None:
            raise NotFound("Sample not found.")
        state: State = row.state
    elif text_or_state is not None:
        state = text_or_state
    else:
        raise NotFound("Send some text or pick a sample.")
    check_length(state)

    policy_and_version = latest_policy(session, project)
    lanes: list[Lane] = ["jev_labels", "jev"] + (["sys1"] if providers.sys1 else [])
    # Lanes share one session but never await between touching it, so gather is safe on a single thread.
    results = await asyncio.gather(
        *(
            run_lane(
                session,
                providers,
                project,
                state,
                lane,
                "playground",
                policy_and_version=policy_and_version,
                dataset_row_id=sample_id,
            )
            for lane in lanes
        )
    )
    if row is None:
        return TryResult(results=list(results))

    template = _flagship(project)
    recorded: dict[str, str] = {}
    recorded_is_fixture = False
    if template and template.flagship:
        flagship = template.flagship
        for run in EvalFilesSource(flagship.eval_dir, flagship.eval_models).runs():
            record = next((r for r in run.records if r.id == row.id), None)
            if record:
                recorded[run.model_key] = record.pred
                recorded_is_fixture = recorded_is_fixture or run.is_fixture
    key = next(iter(row.gold), None)
    return TryResult(
        results=list(results),
        gold=row.gold.get(key) if key else None,
        rule_id=row.metadata.get("rule_id"),
        recorded=recorded,
        recorded_is_fixture=recorded_is_fixture,
    )
