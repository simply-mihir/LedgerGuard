"""Clock faults: scheduling decisions must come from one clock, the database's."""

from __future__ import annotations

import ast
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from ledgerguard.config import settings
from ledgerguard.worker.outbox import claim_pending_outbox_events, mark_outbox_failed

ADMIN = settings.coordinator_admin_db_url
OUTBOX_SRC = Path(__file__).resolve().parents[1] / "src/ledgerguard/worker/outbox.py"


@pytest.fixture
def outbox_event():
    agg = str(uuid4())
    with psycopg.connect(ADMIN, autocommit=True) as c:
        outbox_id = c.execute(
            "INSERT INTO outbox_events (aggregate_id, event_type, payload) "
            "VALUES (%s, 'CLOCK_TEST', '{}') RETURNING outbox_id", (agg,)).fetchone()[0]
    yield agg, outbox_id
    with psycopg.connect(ADMIN, autocommit=True) as c:
        c.execute("DELETE FROM outbox_events WHERE aggregate_id = %s", (agg,))


def _next_attempt_offset_s(outbox_id) -> float:
    """Seconds between the database's current time and the event's next_attempt_at."""
    with psycopg.connect(ADMIN) as c:
        return float(c.execute(
            "SELECT EXTRACT(EPOCH FROM (next_attempt_at - clock_timestamp())) "
            "FROM outbox_events WHERE outbox_id = %s", (outbox_id,)).fetchone()[0])


def test_outbox_module_reads_no_process_clock() -> None:
    """Leases and retries are NOW()-based; importing datetime/time here would reintroduce skew."""
    tree = ast.parse(OUTBOX_SRC.read_text())
    imported = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    imported |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert not imported & {"datetime", "time"}, imported


def test_claim_lease_is_measured_on_the_database_clock(outbox_event) -> None:
    agg, outbox_id = outbox_event
    events = claim_pending_outbox_events(settings.coordinator_db_url, aggregate_id=agg,
                                         lock_duration_seconds=30)
    assert [e["outbox_id"] for e in events] == [outbox_id]
    offset = _next_attempt_offset_s(outbox_id)
    assert 27 <= offset <= 30.5, offset  # full lease remains, whatever this process's clock says
    # While leased, a second worker must not receive it (no duplicate delivery).
    assert claim_pending_outbox_events(settings.coordinator_db_url, aggregate_id=agg) == []


def test_failed_event_is_rescheduled_by_the_database_clock(outbox_event) -> None:
    agg, outbox_id = outbox_event
    claim_pending_outbox_events(settings.coordinator_db_url, aggregate_id=agg, lock_duration_seconds=1)
    mark_outbox_failed(settings.coordinator_db_url, outbox_id, retry_delay_seconds=40)
    offset = _next_attempt_offset_s(outbox_id)
    assert 37 <= offset <= 40.5, offset


def test_control_a_lease_stamped_by_a_slow_clock_is_instantly_reclaimable(outbox_event) -> None:
    """What the old app-clock lease did when this process ran an hour behind the database."""
    agg, outbox_id = outbox_event
    claim_pending_outbox_events(settings.coordinator_db_url, aggregate_id=agg, lock_duration_seconds=30)
    with psycopg.connect(ADMIN, autocommit=True) as c:  # 30 s lease stamped on a clock 1 h slow
        c.execute("UPDATE outbox_events SET next_attempt_at = NOW() - interval '1 hour' "
                  "+ interval '30 seconds' WHERE outbox_id = %s", (outbox_id,))
    again = claim_pending_outbox_events(settings.coordinator_db_url, aggregate_id=agg)
    assert [e["outbox_id"] for e in again] == [outbox_id]  # duplicate delivery, the failure mode


APPROVAL_SRC = Path(__file__).resolve().parents[1] / "src/ledgerguard/approval/service.py"


def test_approval_service_reads_no_process_clock() -> None:
    """Approval expiry is NOW()-based; a skewed app clock must not stretch or shrink the window."""
    tree = ast.parse(APPROVAL_SRC.read_text())
    calls = {ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    assert not {c for c in calls if c in {"datetime.now", "time.time", "datetime.utcnow"}}, calls


def test_approval_window_follows_the_database_clock_not_a_skewed_process_clock(monkeypatch) -> None:
    import time as _time

    from ledgerguard.approval.service import (
        SensitiveAction,  # noqa: F401  (import check)
        create_approval_request,
    )

    monkeypatch.setattr(_time, "time", lambda: 0.0)  # process clock wildly wrong (1970)
    action = next(iter(SensitiveAction))
    req = create_approval_request(ADMIN, action_type=action, payload={"k": "v"},
                                  initiator_id=str(uuid4()), initiator_role="ADMIN", ttl_seconds=600)
    with psycopg.connect(ADMIN) as c:
        remaining = float(c.execute(
            "SELECT EXTRACT(EPOCH FROM (expires_at - clock_timestamp())) FROM approval_requests "
            "WHERE request_id = %s", (req["request_id"],)).fetchone()[0])
    assert 590 <= remaining <= 600, remaining
