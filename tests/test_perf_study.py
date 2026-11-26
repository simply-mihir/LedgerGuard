"""Tests for Stage 10 concurrency and performance study harness."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ledgerguard.perf import ALL_PROFILES, run_perf_study, write_study_artifacts


@pytest.mark.integration
def test_perf_study_smoke_generates_raw_and_markdown_artifacts(tmp_path: Path) -> None:
    report = run_perf_study(
        seed=42,
        profiles=list(ALL_PROFILES[:4]),
        worker_levels=[1, 4],
        warmup_ops=1,
        measured_ops=4,
    )
    assert len(report.results) == 8
    paths = write_study_artifacts(report, tmp_path)
    assert paths["json"].exists()
    assert paths["csv"].exists()
    assert paths["svg"].exists()
    assert paths["md"].exists()

    raw = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert len(raw["results"]) == 8
    assert all(r["p95_ms"] >= r["p50_ms"] for r in raw["results"])
