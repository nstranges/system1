"""Training settings that follow the size of the data, kept free of heavy imports so tests can run locally."""
import math

BATCH_SIZE = 16


def plan_hyperparams(n_rows):
    """Pick the epoch ceiling and learning rate from the number of training rows.

    Early stopping decides when a run actually ends, so epochs is only a ceiling. Small sets get a
    high one because they need many passes, large sets a low one because a few passes cover plenty
    of steps. These are starting points, not tuned values.
    """
    if n_rows <= 0:
        raise ValueError("n_rows must be positive")
    max_epochs = min(10, max(3, math.ceil(6000 / n_rows)))
    if n_rows < 2_000:
        learning_rate = 2e-4
    elif n_rows < 20_000:
        learning_rate = 1e-4
    else:
        learning_rate = 5e-5
    return {"max_epochs": max_epochs, "learning_rate": learning_rate, "batch_size": BATCH_SIZE}


class EarlyStopTracker:
    """Tracks the best eval loss and says when it has not improved for `patience` evaluations."""

    def __init__(self, patience = 1, min_delta = 0.0):
        self.patience = patience
        self.min_delta = min_delta
        self.best = math.inf
        self.stale = 0

    def update(self, loss):
        """Record an eval loss. Returns (improved, should_stop)."""
        if loss < self.best - self.min_delta:
            self.best = loss
            self.stale = 0
            return True, False
        self.stale += 1
        return False, self.stale > self.patience - 1
