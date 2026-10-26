from datetime import datetime

from pydantic import BaseModel


class ModelOut(BaseModel):
    """A trained model: a training run that produced an adapter. Its id is the run's report card id."""

    id: str
    project_id: str
    project_name: str
    created_at: datetime
    live: bool
    # From the run's report card, on that project's frozen test examples. None when the row wasn't scored.
    accuracy: float | None
    jev_accuracy: float | None
    test_examples: int | None
    median_latency_ms: float | None
    # Cards are only comparable on the same test set version.
    test_set_version: int
    corrections_used: int | None
    # small, medium or large. None for models trained before sizes existed, which are small.
    size: str | None
    # Live answers from this model that your team checked, and how many of those it had right.
    checked: int
    checked_right: int


class BucketChange(BaseModel):
    key: str
    before: float
    after: float


class Comparison(BaseModel):
    candidate: ModelOut
    live: ModelOut | None
    # False when the test set changed between the two runs, so their scores can't be compared.
    same_test_set: bool
    diff: float | None
    improved: list[BucketChange]
    worsened: list[BucketChange]
    recommend: bool
    sentence: str
