"""Render a policy into Jev's question shape."""

from typing import Literal

from system1.domain.policy import Policy, validate_policy


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
        instructions = {"question": policy.decision_question, "precedence": [r.text for r in policy.rules]}
        criteria = {k: {"covers": by_key[k].covers, "excludes": by_key[k].excludes} for k in keys}
    return {policy.question_key: {"type": "choice", "instructions": instructions, "criteria": criteria}}
