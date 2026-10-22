"""Bootstrap statistics for the report card.

Accuracy is a mean of yes/no outcomes, so resampling the test set is the same as drawing the number of
correct answers from a binomial. That keeps 2,000 resamples fast on thousands of examples and exact.
"""

import random
from collections import Counter, defaultdict

N_BOOT = 2000
LOW_Q, HIGH_Q = 0.025, 0.975


def _interval(samples: list[float], point: float) -> tuple[float, float]:
    samples.sort()
    low = samples[int(LOW_Q * len(samples))]
    high = samples[min(len(samples) - 1, int(HIGH_Q * len(samples)))]
    return min(low, point), max(high, point)


def accuracy_ci(correct: list[bool], n_boot: int = N_BOOT, seed: int = 0) -> tuple[float, float, float]:
    """Accuracy and its 95% bootstrap interval."""
    n = len(correct)
    if n == 0:
        return 0.0, 0.0, 0.0
    k = sum(correct)
    rng = random.Random(seed)
    samples = [rng.binomialvariate(n, k / n) / n for _ in range(n_boot)]
    low, high = _interval(samples, k / n)
    return k / n, low, high


def paired_diff_ci(a: list[bool], b: list[bool], n_boot: int = N_BOOT, seed: int = 0) -> tuple[float, float, float]:
    """How much more often `a` is right than `b` on the same items, with a 95% bootstrap interval.

    Only items where they disagree move the difference, so the resample draws how many of each kind appear.
    """
    if len(a) != len(b):
        raise ValueError("Both runs need the same items.")
    n = len(a)
    if n == 0:
        return 0.0, 0.0, 0.0
    a_only = sum(x and not y for x, y in zip(a, b, strict=True))
    b_only = sum(y and not x for x, y in zip(a, b, strict=True))
    rng = random.Random(seed)
    samples = []
    for _ in range(n_boot):
        drawn_a = rng.binomialvariate(n, a_only / n)
        left = n - drawn_a
        drawn_b = rng.binomialvariate(left, b_only / (n - a_only)) if left and n > a_only else 0
        samples.append((drawn_a - drawn_b) / n)
    point = (a_only - b_only) / n
    low, high = _interval(samples, point)
    return point, low, high


def per_bucket_accuracy(golds: list[str], preds: list[str]) -> dict[str, float]:
    right: dict[str, int] = defaultdict(int)
    total: dict[str, int] = defaultdict(int)
    for gold, pred in zip(golds, preds, strict=True):
        total[gold] += 1
        right[gold] += gold == pred
    return {bucket: right[bucket] / n for bucket, n in total.items()}


def top_confusions(golds: list[str], preds: list[str], k: int = 3) -> list[tuple[str, str, int]]:
    """The most common (right bucket, answered bucket) mix-ups."""
    mixups = Counter((g, p) for g, p in zip(golds, preds, strict=True) if g != p)
    return [(g, p, n) for (g, p), n in mixups.most_common(k)]
