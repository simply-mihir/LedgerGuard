"""The always-on recovery worker: woken by NOTIFY, polls as fallback, retries only transient failures."""

from __future__ import annotations

import threading
import time
from typing import Any
from uuid import UUID, uuid4

import psycopg
import pytest

from ledgerguard.config import settings
from ledgerguard.coordinator.directory_service import provision_account, register_customer
from ledgerguard.coordinator.failpoints import CrashAfterCommitError, FailpointManager
from ledgerguard.coordinator.transfer_coordinator import submit_coordinator_transfer
from ledgerguard.domain.money import AmountPaise
from ledgerguard.participant.account_service import get_account_balance
from ledgerguard.participant.posting_service import simulate_funding
from ledgerguard.worker.daemon import run_worker

pytestmark = pytest.mark.integration
LEDGERS = {"ledger-1": settings.ledger1_db_url, "ledger-2": settings.ledger2_db_url}


def _start(stop: threading.Event, **kw: Any) -> threading.Thread:
    t = threading.Thread(target=lambda: run_worker(settings.coordinator_db_url, LEDGERS, stop, **kw), daemon=True)
    t.start()
    return t


def test_the_worker_sweeps_on_a_timer_and_stops_promptly() -> None:
    calls: list[float] = []
    stop = threading.Event()
    t = _start(stop, poll_interval_s=1.0, sweep=lambda: calls.append(time.monotonic()) or [])
    time.sleep(3.2)
    stop.set()
    t.join(timeout=5)
    assert not t.is_alive()
    assert len(calls) >= 3, "the poll timer alone keeps sweeping"


def test_a_committed_outbox_insert_wakes_the_worker_long_before_its_poll_interval() -> None:
    stamps: list[float] = []
    stop = threading.Event()
    t = _start(stop, poll_interval_s=60.0, sweep=lambda: stamps.append(time.monotonic()) or [])
    time.sleep(1.0)  # initial sweep done; worker is now parked on LISTEN with a 60 s fallback
    before = len(stamps)
    agg = str(uuid4())
    sent = time.monotonic()
    try:
        with psycopg.connect(settings.coordinator_admin_db_url) as c:
            c.execute("INSERT INTO outbox_events (aggregate_id, event_type, payload) VALUES (%s, 'WAKE_TEST', '{}')", (agg,))
            c.commit()
        deadline = time.monotonic() + 5
        while len(stamps) == before and time.monotonic() < deadline:
            time.sleep(0.05)
        assert len(stamps) > before, "worker never woke"
        assert stamps[before] - sent < 3.0
    finally:
        stop.set()
        t.join(timeout=5)
        with psycopg.connect(settings.coordinator_admin_db_url) as c:
            c.execute("DELETE FROM outbox_events WHERE aggregate_id = %s", (agg,))
            c.commit()


def test_a_non_transient_failure_stops_the_worker_but_a_transient_one_is_retried() -> None:
    stop = threading.Event()
    boom = RuntimeError("logic bug")
    errors: list[BaseException] = []

    def target() -> None:
        try:
            run_worker(settings.coordinator_db_url, LEDGERS, stop, poll_interval_s=1.0,
                       sweep=lambda: (_ for _ in ()).throw(boom))
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(timeout=5)
    assert errors == [boom], "a non-infrastructure error must surface, not be swallowed and retried"

    attempts: list[int] = []

    def flaky() -> list[dict[str, Any]]:
        attempts.append(1)
        if len(attempts) < 3:
            raise psycopg.errors.AdminShutdown("terminating connection due to administrator command")
        return []

    stop2 = threading.Event()
    t2 = _start(stop2, poll_interval_s=1.0, backoff_s=0.1, sweep=flaky)
    time.sleep(1.5)
    stop2.set()
    t2.join(timeout=5)
    assert len(attempts) >= 3, "transient failures are retried after a backoff"


def test_the_worker_forward_recovers_a_crashed_transfer_without_being_polled() -> None:
    coord = settings.coordinator_db_url
    c1 = register_customer(coord, "Daemon A", f"daemon-a-{uuid4()}@t.com")
    c2 = register_customer(coord, "Daemon B", f"daemon-b-{uuid4()}@t.com")
    alice = UUID(str(provision_account(coord, LEDGERS, UUID(str(c1["customer_id"])), "ledger-1", currency="INR")["account_id"]))
    bob = UUID(str(provision_account(coord, LEDGERS, UUID(str(c2["customer_id"])), "ledger-2", currency="INR")["account_id"]))
    simulate_funding(settings.ledger1_db_url, alice, AmountPaise(50_000))

    stop = threading.Event()
    t = _start(stop, poll_interval_s=60.0, min_age_seconds=0.5)  # only NOTIFY can wake it in time
    time.sleep(1.0)
    tid = uuid4()
    fp = FailpointManager()
    fp.set_failpoint("FAIL_AFTER_COMMIT_BEFORE_SOURCE_CONFIRM", tid)
    try:
        try:
            submit_coordinator_transfer(coord, LEDGERS, idempotency_key=f"daemon-{uuid4()}", source_account_id=alice,
                                        destination_account_id=bob, amount=AmountPaise(12_000), transfer_id=tid,
                                        failpoint_mgr=fp)
        except CrashAfterCommitError:
            pass
        state = None
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            with psycopg.connect(settings.coordinator_admin_db_url) as c:
                state = c.execute("SELECT state FROM transfers WHERE transfer_id = %s", (tid,)).fetchone()[0]  # type: ignore[index]
            if state == "SETTLED":
                break
            time.sleep(0.25)
        assert state == "SETTLED", f"worker did not recover the crashed transfer (state={state})"
    finally:
        stop.set()
        t.join(timeout=10)
    assert get_account_balance(settings.ledger1_db_url, alice).posted_balance_minor == 38_000  # exactly one debit
    assert get_account_balance(settings.ledger2_db_url, bob).posted_balance_minor == 12_000
