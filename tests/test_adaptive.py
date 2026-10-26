import pytest

from adaptive import EarlyStopTracker, plan_hyperparams


def test_small_sets_get_more_epochs_than_large_ones():
    small, large = plan_hyperparams(300), plan_hyperparams(50_000)
    assert small["max_epochs"] == 10
    assert large["max_epochs"] == 3
    assert small["learning_rate"] > large["learning_rate"]


def test_epoch_ceiling_stays_in_bounds():
    for n in (1, 50, 500, 5_000, 10**6):
        assert 3 <= plan_hyperparams(n)["max_epochs"] <= 10


def test_rejects_empty_data():
    with pytest.raises(ValueError):
        plan_hyperparams(0)


def test_stops_after_patience_runs_out():
    tracker = EarlyStopTracker(patience = 1)
    assert tracker.update(1.0) == (True, False)
    assert tracker.update(0.8) == (True, False)
    assert tracker.update(0.9) == (False, True)
    assert tracker.best == 0.8


def test_patience_two_tolerates_one_bad_eval():
    tracker = EarlyStopTracker(patience = 2)
    tracker.update(1.0)
    assert tracker.update(1.1) == (False, False)
    assert tracker.update(0.9) == (True, False)
    assert tracker.update(1.0) == (False, False)
    assert tracker.update(1.0) == (False, True)
