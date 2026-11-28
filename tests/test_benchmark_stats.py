"""Unit tests for the benchmark statistics helpers (no database)."""

from __future__ import annotations

import math

from ledgerguard.comparison.stats import distinguishable, summarize, t_critical_95


def test_summarize_matches_hand_computation() -> None:
    mean, sd, lo, hi = summarize([10.0, 12.0, 14.0])
    assert mean == 12.0 and math.isclose(sd, 2.0)
    half = t_critical_95(2) * 2.0 / math.sqrt(3)  # 4.303 * 2 / sqrt(3)
    assert math.isclose(lo, 12.0 - half) and math.isclose(hi, 12.0 + half)


def test_single_sample_has_unbounded_interval() -> None:
    mean, sd, lo, hi = summarize([5.0])
    assert (mean, sd) == (5.0, 0.0) and lo == -math.inf and hi == math.inf


def test_t_critical_decreases_toward_normal() -> None:
    assert t_critical_95(1) > t_critical_95(5) > t_critical_95(30) > 1.96 - 1e-9
    assert t_critical_95(500) == 1.96


def test_distinguishable_requires_non_overlapping_intervals() -> None:
    assert distinguishable((1.0, 2.0), (3.0, 4.0))
    assert not distinguishable((1.0, 3.0), (2.0, 4.0))
