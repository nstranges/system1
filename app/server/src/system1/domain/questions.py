"""Render a policy into Jev's question shape."""

from typing import Literal

from system1.domain.policy import Option, Policy, validate_policy


def _described(option: Option) -> str | dict:
    """The bucket's name, plus what it covers and excludes when written. Jev never loses the readable name, so a
    bucket nobody described is shown to it the same way as in the buckets-only question."""
    extra = {k: v for k, v in (("covers", option.covers), ("excludes", option.excludes)) if v}
    return {"name": option.name, **extra} if extra else option.name


def build_questions(policy: Policy, variant: Literal["labels", "policy"], order: list[str] | None = None) -> dict:
    issues = validate_policy(policy)
    if issues:
        raise ValueError("; ".join(f"{i.path}: {i.message}" for i in issues))

    by_key = {o.key: o for o in policy.options}
    keys = order or [o.key for o in policy.options]
    if variant == "labels":
        instructions: str | dict = policy.decision_question
        criteria = {k: by_key[k].name for k in keys}
    else:
        instructions = {
            "question": policy.decision_question,
            "guidelines": list(policy.guidelines),
            "precedence": [r.text for r in policy.rules],
        }
        instructions = {k: v for k, v in instructions.items() if v}
        criteria = {k: _described(by_key[k]) for k in keys}
    return {policy.question_key: {"type": "choice", "instructions": instructions, "criteria": criteria}}
