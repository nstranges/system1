from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from system1.domain.policy import Policy, PolicyIssue

Lane = Literal["jev", "sys1", "auto"]


class ProjectCreate(BaseModel):
    name: str
    template_id: str | None = None
    description: str | None = None


class ProjectPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    default_lane: Lane | None = None


class ProjectOut(BaseModel):
    id: str
    name: str
    description: str | None
    template_id: str | None
    stage: str
    default_lane: str
    live_model_label: str | None
    created_at: datetime


class PolicyOut(BaseModel):
    policy: Policy
    version: int
    issues: list[PolicyIssue]


class PolicyIn(BaseModel):
    policy: Policy


class TemplateOut(BaseModel):
    id: str
    name: str
    summary: str
    fit: str
    fit_reasons: list[str]
    sample_inputs: list[str]
    flagship: bool


class SampleOut(BaseModel):
    id: str
    state: str | dict | list


class TryIn(BaseModel):
    text: str | None = None
    sample_id: str | None = None
