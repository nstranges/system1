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
