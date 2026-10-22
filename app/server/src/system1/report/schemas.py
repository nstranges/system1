from typing import Literal

from pydantic import BaseModel, Field

RowKey = Literal["sys1", "jev", "jev_labels", "base"]


class ReportRow(BaseModel):
    key: RowKey
    label: str
    # ok: scored. preview/unavailable: there is no model to score. errored: too many answers failed to trust the score.
    status: Literal["ok", "preview", "unavailable", "errored"]
    message: str | None = None
    accuracy: float | None = None
    ci_low: float | None = None
    ci_high: float | None = None
    n: int | None = None
    errors: int = 0
    median_latency_ms: float | None = None


class Verdict(BaseModel):
    winner: Literal["sys1", "jev", "inconclusive", "none"]
    diff: float | None = None
    ci_low: float | None = None
    ci_high: float | None = None
    sentence: str


class Confusion(BaseModel):
    gold: str
    pred: str
    count: int


class ReportDetails(BaseModel):
    # By row key. Only rows that were scored appear.
    per_bucket: dict[str, dict[str, float]] = Field(default_factory=dict)
    confusions: dict[str, list[Confusion]] = Field(default_factory=dict)
    test_per_bucket: dict[str, int] = Field(default_factory=dict)
    # Where "your model" came from: the trainer that ran and the adapter it produced, if any.
    trainer: str | None = None
    adapter_ref: str | None = None


class Report(BaseModel):
    available: bool
    rows: list[ReportRow] = Field(default_factory=list)
    verdict: Verdict | None = None
    details: ReportDetails = Field(default_factory=ReportDetails)
    is_preview: bool = False
    # Recorded sample numbers rather than a run made here; the page shows a banner.
    is_fixture: bool = False
    test_set_version: int | None = None
    too_few_test: bool = False
    job_id: str | None = None
