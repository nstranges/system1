"""Deterministic evaluation of rules-as-data against a dict of facts."""

from typing import Any

from pydantic import BaseModel

from system1.domain.policy import AllOf, AnyOf, Condition, Leaf, Rule


class RuleMatch(BaseModel):
    label: str
    rule_id: str


def _leaf(leaf: Leaf, facts: dict) -> bool:
    actual = facts.get(leaf.field)
    if leaf.op == "is_null":
        return actual is None
    # Unknown means no: a missing fact never satisfies a comparison.
    if actual is None:
        return False
    try:
        match leaf.op:
            case "eq":
                return actual == leaf.value
            case "ne":
                return actual != leaf.value
            case "gt":
                return actual > leaf.value
            case "gte":
                return actual >= leaf.value
            case "lt":
                return actual < leaf.value
            case "lte":
                return actual <= leaf.value
            case "in":
                return actual in leaf.value
    except TypeError:
        return False
    return False


def _holds(cond: Condition, facts: dict) -> bool:
    if isinstance(cond, Leaf):
        return _leaf(cond, facts)
    if isinstance(cond, AllOf):
        return all(_holds(c, facts) for c in cond.all)
    if isinstance(cond, AnyOf):
        return any(_holds(c, facts) for c in cond.any)
    return not _holds(cond.not_, facts)


def evaluate(rules: list[Rule], facts: dict) -> RuleMatch | None:
    for rule in rules:
        if rule.when is None or _holds(rule.when, facts):
            return RuleMatch(label=rule.label, rule_id=rule.id)
    return None


def is_fully_testable(rules: list[Rule]) -> bool:
    """True when every rule except a final catch-all has a condition."""
    return all(rule.when is not None for rule in rules[:-1])


def _collect(cond: Condition, out: dict[str, list]) -> None:
    if isinstance(cond, Leaf):
        values = cond.value if cond.op == "in" else [cond.value]
        for value in values if isinstance(values, list) else [values]:
            if cond.op != "is_null" and value not in out.setdefault(cond.field, []):
                out[cond.field].append(value)
    elif isinstance(cond, AllOf):
        for c in cond.all:
            _collect(c, out)
    elif isinstance(cond, AnyOf):
        for c in cond.any:
            _collect(c, out)
    else:
        _collect(cond.not_, out)


def thresholds(rules: list[Rule]) -> dict[str, list[Any]]:
    """The literal values each field is compared against, for boundary sampling."""
    out: dict[str, list] = {}
    for rule in rules:
        if rule.when is not None:
            _collect(rule.when, out)
    return out
