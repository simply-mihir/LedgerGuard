"""Outbox LISTEN/NOTIFY: a committed event wakes a waiter promptly; a rolled-back one never does."""

from __future__ import annotations

import threading
import time
from uuid import uuid4

import psycopg
import pytest

from ledgerguard.config import settings
from ledgerguard.worker.outbox import record_outbox_event, wait_for_outbox_work

pytestmark = pytest.mark.integration

ADMIN = settings.coordinator_admin_db_url


def _cleanup(aggregate_id: str) -> None:
    with psycopg.connect(ADMIN) as c:
        c.execute("DELETE FROM outbox_events WHERE aggregate_id = %s", (aggregate_id,))


def _enqueue(aggregate_id: str, commit: bool) -> None:
    with psycopg.connect(ADMIN) as c:
        record_outbox_event(c, "outbox_events", aggregate_id, "NOTIFY_TEST", {})
        if commit:
            c.commit()
        else:
            c.rollback()


def test_a_committed_event_wakes_a_waiter_well_before_a_poll_interval() -> None:
    agg = str(uuid4())
    result: dict[str, object] = {}

    def waiter() -> None:
        start = time.monotonic()
        result["woken"] = wait_for_outbox_work(ADMIN, timeout_seconds=10)
        result["elapsed"] = time.monotonic() - start

    t = threading.Thread(target=waiter)
    t.start()
    time.sleep(0.5)  # let LISTEN register
    sent = time.monotonic()
    try:
        _enqueue(agg, commit=True)
        t.join(timeout=10)
        assert result["woken"] is True
        assert time.monotonic() - sent < 1.0, "woken by notification, not by the 10 s timeout"
    finally:
        _cleanup(agg)


def test_a_rolled_back_event_never_wakes_anyone() -> None:
    agg = str(uuid4())
    result: dict[str, object] = {}
    t = threading.Thread(target=lambda: result.update(woken=wait_for_outbox_work(ADMIN, timeout_seconds=1.5)))
    t.start()
    time.sleep(0.5)
    _enqueue(agg, commit=False)
    t.join(timeout=10)
    assert result["woken"] is False


def test_an_idle_wait_times_out_so_callers_can_fall_back_to_polling() -> None:
    start = time.monotonic()
    assert wait_for_outbox_work(ADMIN, timeout_seconds=0.5) is False
    assert 0.4 <= time.monotonic() - start < 3
