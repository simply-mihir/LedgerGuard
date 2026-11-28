"""Real PostgreSQL concurrency and transient-retry tests for opposite-direction transfers."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from uuid import UUID, uuid4

import psycopg
import pytest

from ledgerguard.audit import verify_all_ledgers
from ledgerguard.config import settings
from ledgerguard.coordinator.directory_service import provision_account, register_customer
from ledgerguard.coordinator.reconciliation import run_cross_ledger_reconciliation
from ledgerguard.coordinator.transfer_coordinator import submit_coordinator_transfer
from ledgerguard.db.pool import get_db_connection
from ledgerguard.db.retry import TransientRetryExhaustedError, run_with_transient_retry
from ledgerguard.domain.money import AmountPaise
from ledgerguard.participant.account_service import get_account_balance
from ledgerguard.participant.posting_service import simulate_funding
from ledgerguard.participant.transfer_service import InsufficientFundsError
from ledgerguard.participant.workflow_handler import (
    handle_destination_confirm,
    handle_destination_prepare,
    handle_source_confirm,
    handle_source_prepare,
)


@pytest.mark.concurrency
@pytest.mark.integration
def test_sustained_opposite_direction_cross_ledger_transfers_no_deadlock_failures() -> None:
    """Verify sustained concurrent A->B and B->A transfers complete with zero caller failures and zero invariant violations."""
    ledger_urls = {"ledger-1": settings.ledger1_db_url, "ledger-2": settings.ledger2_db_url}
    c1 = register_customer(settings.coordinator_db_url, "Conc Alice", f"conc-a-{uuid4()}@test.local")
    c2 = register_customer(settings.coordinator_db_url, "Conc Bob", f"conc-b-{uuid4()}@test.local")
    a1 = provision_account(settings.coordinator_db_url, ledger_urls, UUID(str(c1["customer_id"])), "ledger-1")
    a2 = provision_account(settings.coordinator_db_url, ledger_urls, UUID(str(c2["customer_id"])), "ledger-2")
    acct_a = UUID(str(a1["account_id"]))
    acct_b = UUID(str(a2["account_id"]))

    simulate_funding(settings.ledger1_db_url, acct_a, AmountPaise(500_000))
    simulate_funding(settings.ledger2_db_url, acct_b, AmountPaise(500_000))

    total_ops = 40  # 20 A->B, 20 B->A
    barrier = threading.Barrier(10)

    def run_transfer(idx: int) -> dict:
        if idx < 10:
            barrier.wait(timeout=10.0)
        src, dst = (acct_a, acct_b) if idx % 2 == 0 else (acct_b, acct_a)
        return submit_coordinator_transfer(
            settings.coordinator_db_url,
            ledger_urls,
            idempotency_key=f"conc-opp-{idx}-{uuid4()}",
            source_account_id=src,
            destination_account_id=dst,
            amount=AmountPaise(100),
        )

    with ThreadPoolExecutor(max_workers=10) as pool:
        futs = [pool.submit(run_transfer, i) for i in range(total_ops)]
        results = [fut.result(timeout=30.0) for fut in as_completed(futs, timeout=30.0)]

    assert len(results) == total_ops
    assert all(r["status"] == "SETTLED" for r in results)

    bal_a = get_account_balance(settings.ledger1_db_url, acct_a)
    bal_b = get_account_balance(settings.ledger2_db_url, acct_b)
    assert bal_a.posted_balance_minor == 500_000
    assert bal_b.posted_balance_minor == 500_000
    assert bal_a.held_amount_minor == 0
    assert bal_b.held_amount_minor == 0
    assert bal_a.available_balance_minor >= 0
    assert bal_b.available_balance_minor >= 0

    recon = run_cross_ledger_reconciliation(settings.coordinator_db_url, ledger_urls, drained=False)
    assert recon.status == "PASS", f"Reconciliation findings: {recon.findings}"
    assert recon.clearing_balance_sum == 0
    assert verify_all_ledgers()["status"] == "PASS"


@pytest.mark.integration
def test_transient_retry_exactly_once_and_non_retryable_errors() -> None:
    """Verify 40P01 retries preserve idempotency with zero duplicate journals/holds, while permanent errors are not retried."""
    ledger_urls = {"ledger-1": settings.ledger1_db_url, "ledger-2": settings.ledger2_db_url}
    c1 = register_customer(settings.coordinator_db_url, "Retry Alice", f"ret-a-{uuid4()}@test.local")
    c2 = register_customer(settings.coordinator_db_url, "Retry Bob", f"ret-b-{uuid4()}@test.local")
    a1 = provision_account(settings.coordinator_db_url, ledger_urls, UUID(str(c1["customer_id"])), "ledger-1")
    a2 = provision_account(settings.coordinator_db_url, ledger_urls, UUID(str(c2["customer_id"])), "ledger-2")
    src_id = UUID(str(a1["account_id"]))
    dst_id = UUID(str(a2["account_id"]))
    simulate_funding(settings.ledger1_db_url, src_id, AmountPaise(5_000))

    tx_id = uuid4()
    handle_source_prepare(
        settings.ledger1_db_url,
        command_id=f"sp-{tx_id}",
        transfer_id=tx_id,
        source_account_id=src_id,
        dest_account_id=dst_id,
        amount_minor=1_000,
    )

    # Simulate a transient 40P01 deadlock on first attempt before real source_confirm succeeds
    attempts = {"n": 0}

    def flaky_confirm() -> dict:
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise psycopg.errors.DeadlockDetected("simulated transient deadlock")
        return handle_source_confirm(settings.ledger1_db_url, command_id=f"sc-{tx_id}", transfer_id=tx_id)

    res = run_with_transient_retry(flaky_confirm, operation_name="TEST_CONFIRM", max_retries=2, base_delay_ms=1.0)
    assert res["status"] == "CONFIRMED"
    assert attempts["n"] == 2

    # Settle destination side so cross-ledger clearing remains zero-sum
    handle_destination_prepare(
        settings.ledger2_db_url,
        command_id=f"dp-{tx_id}",
        transfer_id=tx_id,
        source_account_id=src_id,
        dest_account_id=dst_id,
        amount_minor=1_000,
    )
    handle_destination_confirm(settings.ledger2_db_url, command_id=f"dc-{tx_id}", transfer_id=tx_id)

    # Verify exactly 1 settlement journal and 0 active holds
    with get_db_connection(settings.ledger1_db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS cnt FROM journal_headers WHERE transfer_id = %s;", (tx_id,))
            row1 = cur.fetchone()
            assert row1 is not None and row1["cnt"] == 1
            cur.execute("SELECT COUNT(*) AS cnt FROM holds WHERE transfer_id = %s AND status = 'ACTIVE';", (tx_id,))
            row2 = cur.fetchone()
            assert row2 is not None and row2["cnt"] == 0

    # Retry exhaustion is bounded and observable
    exhaust_attempts = {"n": 0}

    def always_deadlock() -> None:
        exhaust_attempts["n"] += 1
        raise psycopg.errors.DeadlockDetected("persistent deadlock")

    with pytest.raises(TransientRetryExhaustedError) as exc_info:
        run_with_transient_retry(always_deadlock, operation_name="EXHAUST_TEST", max_retries=2, base_delay_ms=1.0)
    assert exc_info.value.attempts == 3
    assert exhaust_attempts["n"] == 3

    # Permanent / domain errors are NEVER retried
    perm_attempts = {"n": 0}

    def insufficient_funds() -> None:
        perm_attempts["n"] += 1
        raise InsufficientFundsError("not enough balance")

    with pytest.raises(InsufficientFundsError):
        run_with_transient_retry(insufficient_funds, operation_name="PERM_TEST", max_retries=3, base_delay_ms=1.0)
    assert perm_attempts["n"] == 1
