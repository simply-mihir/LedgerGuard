"""Isolation-level study: every anomaly is reproduced deterministically, then shown prevented."""

from __future__ import annotations

import pytest
from psycopg import IsolationLevel

from ledgerguard.isolation.study import (
    ABORTED_RETRY_OK,
    ANOMALY,
    LEVELS,
    SAFE,
    IsolationReport,
    real_posting,
    run_isolation_study,
)

RC, RR, SER = "READ COMMITTED", "REPEATABLE READ", "SERIALIZABLE"

# PostgreSQL's documented behaviour, as observed through two real interleaved sessions.
EXPECTED: dict[tuple[str, str], tuple[str, str, str]] = {
    ("lost_update", "none"): (ANOMALY, ABORTED_RETRY_OK, ABORTED_RETRY_OK),
    ("lost_update", "select_for_update"): (SAFE, ABORTED_RETRY_OK, ABORTED_RETRY_OK),
    ("lost_update", "atomic_update"): (SAFE, ABORTED_RETRY_OK, ABORTED_RETRY_OK),
    ("write_skew", "none"): (ANOMALY, ANOMALY, ABORTED_RETRY_OK),
    ("write_skew", "lock_both_rows"): (SAFE, ABORTED_RETRY_OK, ABORTED_RETRY_OK),
    ("non_repeatable_read", "none"): (ANOMALY, SAFE, SAFE),
    ("phantom_read", "none"): (ANOMALY, SAFE, SAFE),
}


@pytest.fixture(scope="module")
def report() -> IsolationReport:
    return run_isolation_study()


def test_full_anomaly_matrix_matches_postgres_semantics(report: IsolationReport) -> None:
    matrix = report.matrix()
    assert set(matrix) == set(EXPECTED)
    for key, (rc, rr, ser) in EXPECTED.items():
        assert (matrix[key][RC], matrix[key][RR], matrix[key][SER]) == (rc, rr, ser), key


def test_write_skew_is_only_stopped_by_serializable_or_locks(report: IsolationReport) -> None:
    """The one anomaly REPEATABLE READ still allows: disjoint-row writes under a joint rule."""
    skew = report.matrix()[("write_skew", "none")]
    assert skew[RR] == ANOMALY
    assert skew[SER] == ABORTED_RETRY_OK
    cells = [c for c in report.cells if c.scenario == "write_skew" and c.mitigation == "none"]
    violated = next(c for c in cells if c.level == RC)
    assert violated.detail["joint_total_minor"] == -60


def test_lost_update_detail_shows_stale_write(report: IsolationReport) -> None:
    cell = next(c for c in report.cells
                if c.scenario == "lost_update" and c.mitigation == "none" and c.level == RC)
    assert cell.detail == {"final_balance_minor": 50, "expected_minor": 20}


def test_real_post_journal_never_overdraws_at_any_isolation_level(report: IsolationReport) -> None:
    assert [r.level for r in report.real] == [RC, RR, SER]
    for r in report.real:
        assert r.invariant_holds, r
        assert r.succeeded == r.expected_succeeded
        assert r.succeeded + r.rejected_insufficient == r.workers
        assert r.final_balance_minor == r.funded_minor - r.succeeded * r.amount_minor >= 0


def test_explicit_row_locks_make_read_committed_retry_free() -> None:
    """The kernel's lock discipline gives READ COMMITTED safety without any 40001 retries."""
    result = real_posting(IsolationLevel.READ_COMMITTED, workers=8, funded_for=2)
    assert result.invariant_holds
    assert result.retries == 0


def test_levels_cover_the_three_postgres_behaviours() -> None:
    assert len(LEVELS) == 3
