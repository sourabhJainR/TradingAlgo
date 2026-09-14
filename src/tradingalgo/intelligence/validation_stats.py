"""Small dependency-free statistical helpers for research validation."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from statistics import mean
from typing import Sequence


@dataclass(frozen=True)
class StatisticalSummary:
    sample_size: int
    mean: float
    t_statistic: float
    normal_p_value: float
    bootstrap_ci_low: float
    bootstrap_ci_high: float
    sign_flip_p_value: float


def summarize(values: Sequence[float], *, samples: int = 2000, seed: int = 42) -> StatisticalSummary:
    xs = [float(v) for v in values]
    n = len(xs)
    if not n:
        return StatisticalSummary(0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0)
    observed = mean(xs)
    sd = _stdev(xs)
    t = observed / (sd / math.sqrt(n)) if sd and n > 1 else 0.0
    p = 2.0 * (1.0 - _normal_cdf(abs(t))) if n > 1 else 1.0
    rng = random.Random(seed)
    count = max(1, samples)
    boot = sorted(mean(rng.choice(xs) for _ in xs) for _ in range(count))
    lo = boot[max(0, int(.025 * count) - 1)]
    hi = boot[min(count - 1, int(.975 * count))]
    extreme = 0
    for _ in range(count):
        null_mean = mean(x if rng.getrandbits(1) else -x for x in xs)
        if abs(null_mean) >= abs(observed):
            extreme += 1
    return StatisticalSummary(n, observed, t, p, lo, hi, (extreme + 1) / (count + 1))


def benjamini_hochberg(p_values: Sequence[float]) -> tuple[float, ...]:
    """Return FDR-adjusted p-values in original order."""
    indexed = sorted(enumerate(float(p) for p in p_values), key=lambda item: item[1])
    adjusted = [1.0] * len(indexed)
    running = 1.0
    n = len(indexed)
    for rank in range(n, 0, -1):
        index, p = indexed[rank - 1]
        running = min(running, p * n / rank)
        adjusted[index] = min(1.0, running)
    return tuple(adjusted)


def _stdev(values: Sequence[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = mean(values)
    return math.sqrt(sum((x - m) ** 2 for x in values) / (len(values) - 1))


def _normal_cdf(x: float) -> float:
    return .5 * (1.0 + math.erf(x / math.sqrt(2.0)))
