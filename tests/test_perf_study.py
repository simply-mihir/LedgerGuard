"""Tests for Stage 10 concurrency and performance study harness and provenance."""

from __future__ import annotations

import csv
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from ledgerguard.perf import (
    ALL_PROFILES,
    DirtyWorkingTreeError,
    InvocationMetadata,
    ProfileResult,
    SourceProvenance,
    StudyReport,
    build_reproduce_command,
    collect_source_provenance,
    run_perf_study,
    write_study_artifacts,
)

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_v2_perf_study.py"
_SPEC = importlib.util.spec_from_file_location("run_v2_perf_study", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
run_v2_perf_study = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(run_v2_perf_study)


def _init_temp_git_repo(repo_dir: Path) -> None:
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test Bot"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "bot@example.com"], cwd=repo_dir, check=True, capture_output=True)
    (repo_dir / "README.md").write_text("init\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo_dir, check=True, capture_output=True)


def test_build_reproduce_command_smoke_and_full() -> None:
    smoke_cmd = build_reproduce_command(
        seed=42,
        mode="smoke",
        warmup_ops=2,
        default_measured_ops=6,
        per_profile_ops={"opposite_direction": 100},
        profiles=list(ALL_PROFILES),
        output_directory="docs/performance",
    )
    assert smoke_cmd == (
        "uv run python scripts/run_v2_perf_study.py "
        "--seed 42 --smoke --opposite-ops 100 --warmup 2 --out-dir docs/performance"
    )

    full_cmd = build_reproduce_command(
        seed=7,
        mode="full",
        warmup_ops=3,
        default_measured_ops=20,
        per_profile_ops={"opposite_direction": 50},
        profiles=["uniform_local", "opposite_direction"],
        output_directory="/tmp/out",
    )
    assert full_cmd == (
        "uv run python scripts/run_v2_perf_study.py "
        "--seed 7 --ops 20 --opposite-ops 50 --warmup 3 --out-dir /tmp/out "
        "--profiles uniform_local,opposite_direction"
    )


def test_collect_source_provenance_clean_and_dirty_git_repo(tmp_path: Path) -> None:
    _init_temp_git_repo(tmp_path)
    clean_prov = collect_source_provenance(tmp_path)
    assert re.fullmatch(r"[0-9a-f]{40}", clean_prov.git_sha)
    assert re.fullmatch(r"[0-9a-f]{40}", clean_prov.git_tree)
    assert clean_prov.working_tree_clean is True

    # Dirty the repo
    (tmp_path / "README.md").write_text("modified\n", encoding="utf-8")
    dirty_prov = collect_source_provenance(tmp_path)
    assert dirty_prov.git_sha == clean_prov.git_sha
    assert dirty_prov.git_tree == clean_prov.git_tree
    assert dirty_prov.working_tree_clean is False


def test_run_perf_study_rejects_dirty_tree_and_allows_override(tmp_path: Path) -> None:
    _init_temp_git_repo(tmp_path)
    (tmp_path / "README.md").write_text("dirty\n", encoding="utf-8")

    with pytest.raises(DirtyWorkingTreeError, match="dirty working tree"):
        run_perf_study(
            seed=42,
            profiles=["uniform_local"],
            worker_levels=[1],
            warmup_ops=0,
            measured_ops=1,
            allow_dirty=False,
            repo_root=tmp_path,
        )

    # With allow_dirty=True, provenance check passes and marks working_tree_clean=False
    with (
        patch("ledgerguard.perf.study.register_customer", return_value={"customer_id": "00000000-0000-0000-0000-000000000001"}),
        patch("ledgerguard.perf.study.provision_account", return_value={"account_id": "00000000-0000-0000-0000-000000000002"}),
        patch("ledgerguard.perf.study.simulate_funding"),
        patch("ledgerguard.perf.study.create_account_snapshot"),
        patch("ledgerguard.perf.study.execute_local_transfer"),
    ):
        report = run_perf_study(
            seed=42,
            profiles=["uniform_local"],
            worker_levels=[1],
            warmup_ops=0,
            measured_ops=1,
            allow_dirty=True,
            repo_root=tmp_path,
        )
    assert report.schema_version == 2
    assert report.source.working_tree_clean is False
    assert re.fullmatch(r"[0-9a-f]{40}", report.source.git_sha)


def test_retry_metric_split_and_no_cross_window_leakage(tmp_path: Path) -> None:
    _init_temp_git_repo(tmp_path)
    # Sequence of get_transient_retry_stats calls:
    # Window 1 (uniform_local, w=1): before=(1, 2), after=(3, 5) -> deadlock_retries=2, serialization_retries=3, total=5
    # Window 2 (uniform_local, w=10): before=(10, 10), after=(10, 11) -> deadlock_retries=0, serialization_retries=1, total=1
    stats_seq = iter(
        [
            {"40P01": 1, "40001": 2},
            {"40P01": 3, "40001": 5},
            {"40P01": 10, "40001": 10},
            {"40P01": 10, "40001": 11},
        ]
    )

    with (
        patch("ledgerguard.perf.study.register_customer", return_value={"customer_id": "00000000-0000-0000-0000-000000000001"}),
        patch("ledgerguard.perf.study.provision_account", return_value={"account_id": "00000000-0000-0000-0000-000000000002"}),
        patch("ledgerguard.perf.study.simulate_funding"),
        patch("ledgerguard.perf.study.create_account_snapshot"),
        patch("ledgerguard.perf.study.execute_local_transfer"),
        patch("ledgerguard.perf.study.get_transient_retry_stats", side_effect=lambda: next(stats_seq)),
    ):
        report = run_perf_study(
            seed=42,
            profiles=["uniform_local"],
            worker_levels=[1, 10],
            warmup_ops=1,
            measured_ops=2,
            per_profile_ops={"opposite_direction": 100},
            mode="smoke",
            repo_root=tmp_path,
        )

    assert len(report.results) == 2
    r0, r1 = report.results
    assert (r0.deadlock_retries, r0.serialization_retries, r0.total_transient_retries) == (2, 3, 5)
    assert (r1.deadlock_retries, r1.serialization_retries, r1.total_transient_retries) == (0, 1, 1)


def test_cli_captures_smoke_and_full_flags(tmp_path: Path) -> None:
    dummy_report = StudyReport(
        schema_version=2,
        generated_at="2026-01-01T00:00:00+00:00",
        source=SourceProvenance(git_sha="a" * 40, git_tree="b" * 40, working_tree_clean=True),
        invocation=InvocationMetadata(
            command="uv run python scripts/run_v2_perf_study.py --seed 42 --smoke --opposite-ops 100 --warmup 2 --out-dir docs/performance",
            seed=42,
            mode="smoke",
            worker_levels=[1, 10],
            warmup_ops=2,
            default_measured_ops=6,
            per_profile_ops={"opposite_direction": 100},
            profiles=list(ALL_PROFILES),
            output_directory=str(tmp_path),
        ),
        seed=42,
        environment={"os": "Linux"},
        results=[],
    )

    with (
        patch.object(run_v2_perf_study, "run_perf_study", return_value=dummy_report) as mock_run,
        patch.object(
            sys,
            "argv",
            [
                "run_v2_perf_study.py",
                "--seed",
                "42",
                "--smoke",
                "--opposite-ops",
                "100",
                "--warmup",
                "2",
                "--out-dir",
                str(tmp_path),
                "--allow-dirty",
            ],
        ),
    ):
        run_v2_perf_study.main()

    mock_run.assert_called_once_with(
        seed=42,
        profiles=list(ALL_PROFILES),
        worker_levels=[1, 10],
        warmup_ops=2,
        measured_ops=6,
        per_profile_ops={"opposite_direction": 100},
        mode="smoke",
        output_directory=str(tmp_path),
        allow_dirty=True,
    )

    with (
        patch.object(run_v2_perf_study, "run_perf_study", return_value=dummy_report) as mock_full,
        patch.object(
            sys,
            "argv",
            [
                "run_v2_perf_study.py",
                "--seed",
                "99",
                "--ops",
                "15",
                "--opposite-ops",
                "50",
                "--warmup",
                "3",
                "--profiles",
                "uniform_local,opposite_direction",
                "--out-dir",
                str(tmp_path),
            ],
        ),
    ):
        run_v2_perf_study.main()

    mock_full.assert_called_once_with(
        seed=99,
        profiles=["uniform_local", "opposite_direction"],
        worker_levels=[1, 10, 50],
        warmup_ops=3,
        measured_ops=15,
        per_profile_ops={"opposite_direction": 50},
        mode="full",
        output_directory=str(tmp_path),
        allow_dirty=False,
    )


def test_cli_rejects_unknown_profile() -> None:
    with (
        patch.object(sys, "argv", ["run_v2_perf_study.py", "--profiles", "nonexistent_profile"]),
        pytest.raises(SystemExit) as exc_info,
    ):
        run_v2_perf_study.main()
    assert exc_info.value.code == 2


def test_write_study_artifacts_markdown_json_csv_parity_and_hygiene(tmp_path: Path) -> None:
    cmd = (
        "uv run python scripts/run_v2_perf_study.py "
        "--seed 42 --smoke --opposite-ops 100 --warmup 2 --out-dir docs/performance"
    )
    report = StudyReport(
        schema_version=2,
        generated_at="2026-11-26T00:00:00+00:00",
        source=SourceProvenance(git_sha="1" * 40, git_tree="2" * 40, working_tree_clean=True),
        invocation=InvocationMetadata(
            command=cmd,
            seed=42,
            mode="smoke",
            worker_levels=[1, 10],
            warmup_ops=2,
            default_measured_ops=6,
            per_profile_ops={"opposite_direction": 100},
            profiles=["uniform_local", "opposite_direction"],
            output_directory="docs/performance",
        ),
        seed=42,
        environment={"os": "Darwin", "python": "3.12.13"},
        results=[
            ProfileResult(
                profile="uniform_local",
                workers=1,
                warmup_ops=2,
                measured_ops=6,
                success_count=6,
                failure_count=0,
                error_rate=0.0,
                throughput_tps=50.0,
                p50_ms=10.0,
                p95_ms=15.0,
                p99_ms=15.0,
                max_ms=15.0,
                deadlocks=0,
                deadlock_retries=0,
                serialization_retries=0,
                total_transient_retries=0,
                duration_seconds=0.12,
            ),
            ProfileResult(
                profile="opposite_direction",
                workers=10,
                warmup_ops=2,
                measured_ops=100,
                success_count=100,
                failure_count=0,
                error_rate=0.0,
                throughput_tps=80.0,
                p50_ms=120.0,
                p95_ms=160.0,
                p99_ms=180.0,
                max_ms=190.0,
                deadlocks=0,
                deadlock_retries=1,
                serialization_retries=2,
                total_transient_retries=3,
                duration_seconds=1.25,
            ),
        ],
    )
    paths = write_study_artifacts(report, tmp_path)

    raw_json = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert raw_json["schema_version"] == 2
    assert raw_json["source"]["git_sha"] == "1" * 40
    assert raw_json["source"]["git_tree"] == "2" * 40
    assert raw_json["source"]["working_tree_clean"] is True
    assert raw_json["invocation"]["command"] == cmd

    csv_bytes = paths["csv"].read_bytes()
    assert b"\r\n" not in csv_bytes
    assert b"\r" not in csv_bytes
    assert csv_bytes.endswith(b"\n")

    with paths["csv"].open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        expected_cols = [
            "profile",
            "workers",
            "warmup_ops",
            "measured_ops",
            "success_count",
            "failure_count",
            "error_rate",
            "throughput_tps",
            "p50_ms",
            "p95_ms",
            "p99_ms",
            "max_ms",
            "deadlocks",
            "deadlock_retries",
            "serialization_retries",
            "total_transient_retries",
            "duration_seconds",
        ]
        assert reader.fieldnames == expected_cols
        rows = list(reader)
        assert len(rows) == 2
        assert rows[1]["deadlock_retries"] == "1"
        assert rows[1]["serialization_retries"] == "2"
        assert rows[1]["total_transient_retries"] == "3"

    md_text = paths["md"].read_text(encoding="utf-8")
    assert f"`{raw_json['source']['git_sha']}`" in md_text
    assert f"`{cmd}`" in md_text
    assert "Benchmark schema version:** `2`" in md_text
    assert "Source tree clean:** `true`" in md_text
    assert (
        "Deterministic resource ordering plus bounded transient retry prevented "
        "caller-visible failures in the documented PostgreSQL contention campaign."
    ) in md_text

    # No secrets, env vars, database URLs, or personal paths
    for p in paths.values():
        content = p.read_text(encoding="utf-8")
        assert "/Users/" not in content
        assert "postgresql://" not in content
        assert "password" not in content.lower()


@pytest.mark.integration
def test_perf_study_smoke_generates_raw_and_markdown_artifacts(tmp_path: Path) -> None:
    report = run_perf_study(
        seed=42,
        profiles=list(ALL_PROFILES[:4]),
        worker_levels=[1, 4],
        warmup_ops=1,
        measured_ops=4,
        mode="smoke",
        allow_dirty=True,
    )
    assert report.schema_version == 2
    assert len(report.results) == 8
    paths = write_study_artifacts(report, tmp_path)
    assert all(p.exists() for p in paths.values())

    csv_bytes = paths["csv"].read_bytes()
    assert b"\r\n" not in csv_bytes
    assert b"\r" not in csv_bytes
    assert csv_bytes.endswith(b"\n")

    with paths["csv"].open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == list(ProfileResult.model_fields.keys())
        rows = list(reader)
        assert len(rows) == 8

    raw = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert raw["schema_version"] == 2
    assert len(raw["results"]) == 8
    assert all(r["p95_ms"] >= r["p50_ms"] for r in raw["results"])
    assert all(
        r["total_transient_retries"] == r["deadlock_retries"] + r["serialization_retries"]
        for r in raw["results"]
    )
