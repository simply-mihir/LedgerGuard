"""Server-side time limits: a stuck lock or stalled client becomes a bounded, classified failure."""

from __future__ import annotations

import json
import threading
import time
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from ledgerguard.api.app import create_app
from ledgerguard.config import settings
from ledgerguard.db.pool import get_db_connection
from ledgerguard.db.retry import TransientRetryExhaustedError, run_with_transient_retry
from ledgerguard.domain.constants import SYSTEM_CASH_ACCOUNT_ID
from ledgerguard.domain.money import AmountPaise
from ledgerguard.participant.account_service import create_ledger_account
from ledgerguard.participant.posting_service import simulate_funding

URL = settings.ledger1_db_url


ADMIN_URL = settings.ledger1_admin_db_url  # the app role has no direct table access (by design)


def _connect(options: str, url: str = URL) -> psycopg.Connection:
    return psycopg.connect(url, options=options, autocommit=False)


@pytest.fixture
def funded_account() -> UUID:
    account = create_ledger_account(URL).account_id
    simulate_funding(URL, account, AmountPaise(10_000))
    return account


def _hold_lock(account: UUID) -> psycopg.Connection:
    holder = psycopg.connect(ADMIN_URL, autocommit=False)
    holder.execute(
        "SELECT 1 FROM account_balances WHERE account_id = %s FOR UPDATE", (account,)
    )
    return holder


def _cash_out(conn: psycopg.Connection, account: UUID, amount: int) -> None:
    lines = [
        {"account_id": str(account), "side": "DEBIT", "amount_minor": amount},
        {"account_id": str(SYSTEM_CASH_ACCOUNT_ID), "side": "CREDIT", "amount_minor": amount},
    ]
    conn.execute(
        "SELECT post_journal(%s, NULL, 'CASH_OUT', 'INR', NULL, 'timeout test', %s::jsonb)",
        (uuid4(), json.dumps(lines)),
    )


def _balance(account: UUID) -> int:
    with psycopg.connect(URL) as conn:
        row = conn.execute(
            "SELECT posted_balance_minor FROM account_balances WHERE account_id = %s", (account,)
        ).fetchone()
    assert row is not None
    return int(row[0])


def test_pooled_connections_carry_the_configured_limits() -> None:
    with get_db_connection(URL) as conn:
        got = {
            name: conn.execute(f"SHOW {name}").fetchone()
            for name in ("lock_timeout", "statement_timeout", "idle_in_transaction_session_timeout")
        }
    assert got["lock_timeout"] == {"lock_timeout": "5s"}
    assert got["statement_timeout"] == {"statement_timeout": "1min"}
    assert got["idle_in_transaction_session_timeout"] == {
        "idle_in_transaction_session_timeout": "1min"
    }


def test_zero_disables_a_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "db_lock_timeout_ms", 0)
    assert "-c lock_timeout=0 " in settings.db_session_options() + " "


def test_stuck_lock_fails_fast_and_exhausted_retries_commit_nothing(
    funded_account: UUID,
) -> None:
    holder = _hold_lock(funded_account)
    attempts = 0

    def attempt() -> None:
        nonlocal attempts
        attempts += 1
        with _connect("-c lock_timeout=150") as conn:
            _cash_out(conn, funded_account, 1_000)
            conn.commit()

    started = time.monotonic()
    try:
        with pytest.raises(TransientRetryExhaustedError) as err:
            run_with_transient_retry(attempt, operation_name="timeout_test", max_retries=2,
                                     base_delay_ms=1.0, max_delay_ms=5.0)
    finally:
        holder.rollback()
        holder.close()
    elapsed = time.monotonic() - started
    assert err.value.sqlstate == "55P03"
    assert attempts == 3  # 1 try + 2 retries, then a clean, classified failure
    assert elapsed < 5.0  # bounded by 3 x lock_timeout, not by the holder
    assert _balance(funded_account) == 10_000  # no failed attempt committed anything


def test_lock_timeout_is_retried_until_the_holder_releases(funded_account: UUID) -> None:
    holder = _hold_lock(funded_account)
    threading.Timer(0.5, lambda: (holder.rollback(), holder.close())).start()
    attempts = 0

    def attempt() -> None:
        nonlocal attempts
        attempts += 1
        with _connect("-c lock_timeout=100") as conn:
            _cash_out(conn, funded_account, 1_000)
            conn.commit()

    run_with_transient_retry(attempt, operation_name="timeout_test", max_retries=20,
                             base_delay_ms=20.0, max_delay_ms=50.0)
    assert attempts >= 2  # it really did time out and retry at least once
    assert _balance(funded_account) == 9_000  # applied exactly once


def test_statement_timeout_cancels_and_is_not_retried() -> None:
    attempts = 0

    def attempt() -> None:
        nonlocal attempts
        attempts += 1
        with _connect("-c statement_timeout=100") as conn:
            conn.execute("SELECT pg_sleep(5)")

    started = time.monotonic()
    with pytest.raises(psycopg.errors.QueryCanceled):
        run_with_transient_retry(attempt, operation_name="timeout_test", max_retries=3,
                                 base_delay_ms=1.0, max_delay_ms=5.0)
    assert attempts == 1
    assert time.monotonic() - started < 3.0


def test_idle_in_transaction_session_releases_its_locks(funded_account: UUID) -> None:
    stalled = _connect("-c idle_in_transaction_session_timeout=200", ADMIN_URL)
    try:
        stalled.execute(
            "SELECT 1 FROM account_balances WHERE account_id = %s FOR UPDATE", (funded_account,)
        )
        time.sleep(0.8)  # the "client" stalls while holding the lock
        with _connect("-c lock_timeout=2000") as other:
            _cash_out(other, funded_account, 1_000)  # blocks 2s then fails if the lock is held
            other.commit()
        assert _balance(funded_account) == 9_000
        with pytest.raises(psycopg.Error):  # session terminated by the server
            stalled.execute("SELECT 1")
    finally:
        stalled.close()


@pytest.mark.parametrize(
    "exc",
    [psycopg.errors.LockNotAvailable("x"), psycopg.errors.QueryCanceled("x"),
     TransientRetryExhaustedError("op", "55P03", 4, psycopg.errors.LockNotAvailable("x"))],
)
def test_api_maps_database_time_limits_to_503_without_leaking(exc: Exception) -> None:
    app = create_app()

    def boom() -> None:
        raise exc

    app.add_api_route("/__boom", boom)
    res = TestClient(app).get("/__boom")
    assert res.status_code == 503
    assert res.headers["Retry-After"] == "1"
    assert res.json() == {"detail": "The ledger database is busy. Retry shortly."}
