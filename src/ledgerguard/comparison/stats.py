"""Small, dependency-free summary statistics for repeated benchmark runs."""

from __future__ import annotations

import math
import statistics

# Two-sided 95% Student-t critical values by degrees of freedom (1..30); 1.96 beyond.
_T95 = (
    12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228,
    2.201, 2.179, 2.160, 2.145, 2.131, 2.120, 2.110, 2.101, 2.093, 2.086,
    2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042,
)


def t_critical_95(df: int) -> float:
    if df < 1:
        return math.inf
    return _T95[df - 1] if df <= len(_T95) else 1.96


def summarize(values: list[float]) -> tuple[float, float, float, float]:
    """Return (mean, sample stdev, ci95_low, ci95_high). One sample gives an unbounded CI."""
    n = len(values)
    if n == 0:
        return 0.0, 0.0, 0.0, 0.0
    mean = statistics.fmean(values)
    if n == 1:
        return mean, 0.0, -math.inf, math.inf
    sd = statistics.stdev(values)
    half = t_critical_95(n - 1) * sd / math.sqrt(n)
    return mean, sd, mean - half, mean + half


def distinguishable(a: tuple[float, float], b: tuple[float, float]) -> bool:
    """Conservative test: two 95% intervals that do not overlap are distinguishable."""
    return a[1] < b[0] or b[1] < a[0]
