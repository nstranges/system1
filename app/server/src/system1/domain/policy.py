"""Policy model: the inputs, options and routing rules a team's decision runs on.

Pure Pydantic. Rules are data (a recursive condition tree), so the same policy
can be evaluated, shown to the user and rendered into a model prompt.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MIN_OPTIONS = 2
MAX_OPTIONS = 15


class InputField(BaseModel):
    key: str
    label: str
    type: Literal["enum", "int", "float", "bool", "text"]
    values: list[str] | None = None
    nullable: bool = True
    description: str = ""


class Option(BaseModel):
    key: str
    name: str
    covers: list[str] = Field(default_factory=list)
    excludes: list[str] = Field(default_factory=list)
    example: str = ""


class Leaf(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str
    op: Literal["eq", "ne", "gt", "gte", "lt", "lte", "in", "is_null"]
    value: Any = None


class AllOf(BaseModel):
    model_config = ConfigDict(extra="forbid")
    all: list["Condition"]


class AnyOf(BaseModel):
    model_config = ConfigDict(extra="forbid")
    any: list["Condition"]


class NotOf(BaseModel):
    # `not` is a keyword, so the attribute is `not_` and the JSON key is "not".
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    not_: "Condition" = Field(alias="not")


Condition = Leaf | AllOf | AnyOf | NotOf

AllOf.model_rebuild()
AnyOf.model_rebuild()
NotOf.model_rebuild()


class Rule(BaseModel):
    id: str
    text: str
    label: str
    when: Condition | None = None


class Policy(BaseModel):
    decision_question: str
    question_key: str = "decision"
    inputs: list[InputField] = Field(default_factory=list)
    options: list[Option]
    rules: list[Rule] = Field(default_factory=list)


class PolicyIssue(BaseModel):
    path: str
    message: str


def condition_fields(cond: Condition) -> list[str]:
    """Every input key a condition tree refers to."""
    if isinstance(cond, Leaf):
        return [cond.field]
    if isinstance(cond, AllOf):
        return [f for c in cond.all for f in condition_fields(c)]
    if isinstance(cond, AnyOf):
        return [f for c in cond.any for f in condition_fields(c)]
    return condition_fields(cond.not_)


def validate_policy(policy: Policy) -> list[PolicyIssue]:
    issues: list[PolicyIssue] = []

    count = len(policy.options)
    if count < MIN_OPTIONS or count > MAX_OPTIONS:
        issues.append(PolicyIssue(path="options", message=f"need {MIN_OPTIONS} to {MAX_OPTIONS} options, got {count}"))

    seen: set[str] = set()
    for i, option in enumerate(policy.options):
        if option.key in seen:
            issues.append(PolicyIssue(path=f"options[{i}].key", message=f"duplicate option key '{option.key}'"))
        seen.add(option.key)

    input_keys = {f.key for f in policy.inputs}
    for i, rule in enumerate(policy.rules):
        if rule.label not in seen:
            issues.append(PolicyIssue(path=f"rules[{i}].label", message=f"unknown option '{rule.label}'"))
        if rule.when is not None:
            for name in dict.fromkeys(condition_fields(rule.when)):
                if name not in input_keys:
                    issues.append(PolicyIssue(path=f"rules[{i}].when", message=f"unknown input '{name}'"))
    return issues
