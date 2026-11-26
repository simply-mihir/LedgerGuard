"""Tests for Stage 8 partial/full refunds, concurrent refund limits, and chargeback disputes."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import psycopg
import pytest

from ledgerguard.audit import verify_all_ledgers
from ledgerguard.config import settings
from ledgerguard.coordinator.directory_service import provision_account, register_customer
from ledgerguard.coordinator.reconciliation import run_cross_ledger_reconciliation
from ledgerguard.coordinator.transfer_coordinator import submit_coordinator_transfer
from ledgerguard.disputes import (
    DisputeState,
    RefundLimitExceededError,
    issue_refund,
    open_dispute,
    transition_dispute,
)
from ledgerguard.domain.money import AmountPaise
from ledgerguard.participant.account_service import get_account_balance
from ledgerguard.participant.posting_service import simulate_funding


@pytest.mark.integration
def test_partial_refund_idempotency_and_concurrent_over_refund_prevention() -> None:
    ledger_urls = {"ledger-1": settings.ledger1_db_url, "ledger-2": settings.ledger2_db_url}
    c1 = register_customer(settings.coordinator_db_url, "Ref Alice", f"ref-a-{uuid4()}@test.local")
    c2 = register_customer(settings.coordinator_db_url, "Ref Bob", f"ref-b-{uuid4()}@test.local")
    a1 = provision_account(settings.coordinator_db_url, ledger_urls, UUID(str(c1["customer_id"])), "ledger-1")
    a2 = provision_account(settings.coordinator_db_url, ledger_urls, UUID(str(c2["customer_id"])), "ledger-2")
    src_id = UUID(str(a1["account_id"]))
    dst_id = UUID(str(a2["account_id"]))
    simulate_funding(settings.ledger1_db_url, src_id, AmountPaise(10_000))

    tx_id = uuid4()
    submit_coordinator_transfer(
        settings.coordinator_db_url,
        ledger_urls,
        idempotency_key=f"ref-tx-{tx_id}",
        source_account_id=src_id,
        destination_account_id=dst_id,
        amount=AmountPaise(6_000),
        transfer_id=tx_id,
    )

    # Partial refund of 4000 paise + idempotent replay
    r1 = issue_refund(
        settings.coordinator_db_url,
        ledger_urls,
        original_transfer_id=tx_id,
        amount=AmountPaise(4_000),
        idempotency_key=f"ref-idem-1-{tx_id}",
    )
    r1_dup = issue_refund(
        settings.coordinator_db_url,
        ledger_urls,
        original_transfer_id=tx_id,
        amount=AmountPaise(4_000),
        idempotency_key=f"ref-idem-1-{tx_id}",
    )
    assert r1["refund_id"] == r1_dup["refund_id"]
    assert r1_dup["duplicate_ignored"] is True

    # Concurrent attempts to refund 2000 paise (only one may succeed, the other must be rejected)
    def try_refund(idx: int) -> bool:
        try:
            issue_refund(
                settings.coordinator_db_url,
                ledger_urls,
                original_transfer_id=tx_id,
                amount=AmountPaise(2_000),
                idempotency_key=f"ref-conc-{idx}-{tx_id}",
            )
            return True
        except RefundLimitExceededError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(try_refund, [1, 2]))

    assert outcomes.count(True) == 1
    assert outcomes.count(False) == 1

    # Alice back to 10_000, Bob at 0
    assert get_account_balance(settings.ledger1_db_url, src_id).posted_balance_minor == 10_000
    assert get_account_balance(settings.ledger2_db_url, dst_id).posted_balance_minor == 0


@pytest.mark.integration
def test_chargeback_dispute_lifecycle_and_immutable_events() -> None:
    ledger_urls = {"ledger-1": settings.ledger1_db_url, "ledger-2": settings.ledger2_db_url}
    c1 = register_customer(settings.coordinator_db_url, "Disp Alice", f"disp-a-{uuid4()}@test.local")
    c2 = register_customer(settings.coordinator_db_url, "Disp Bob", f"disp-b-{uuid4()}@test.local")
    a1 = provision_account(settings.coordinator_db_url, ledger_urls, UUID(str(c1["customer_id"])), "ledger-1")
    a2 = provision_account(settings.coordinator_db_url, ledger_urls, UUID(str(c2["customer_id"])), "ledger-2")
    src_id = UUID(str(a1["account_id"]))
    dst_id = UUID(str(a2["account_id"]))
    simulate_funding(settings.ledger1_db_url, src_id, AmountPaise(5_000))

    tx_id = uuid4()
    submit_coordinator_transfer(
        settings.coordinator_db_url,
        ledger_urls,
        idempotency_key=f"disp-tx-{tx_id}",
        source_account_id=src_id,
        destination_account_id=dst_id,
        amount=AmountPaise(3_000),
        transfer_id=tx_id,
    )

    disp = open_dispute(
        settings.coordinator_db_url,
        transfer_id=tx_id,
        amount=AmountPaise(3_000),
        reason_code="FRAUD_UNAUTH",
        actor="operator_1",
        evidence_metadata={"ticket": "CASE-101"},
    )
    did = UUID(str(disp["dispute_id"]))
    transition_dispute(settings.coordinator_db_url, ledger_urls, dispute_id=did, to_state=DisputeState.UNDER_REVIEW, actor="operator_1")
    resolved = transition_dispute(settings.coordinator_db_url, ledger_urls, dispute_id=did, to_state=DisputeState.APPROVED, actor="approver_1")
    assert resolved["state"] == "RESOLVED"
    assert resolved["compensation_transfer_id"] is not None
    assert len(resolved["events"]) == 4  # OPENED, UNDER_REVIEW, APPROVED, RESOLVED

    # Immutable dispute events cannot be modified
    with pytest.raises(psycopg.Error):
        with psycopg.connect(settings.coordinator_db_url) as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE dispute_events SET to_state = 'REJECTED' WHERE dispute_id = %s;", (did,))
            conn.commit()

    assert run_cross_ledger_reconciliation(settings.coordinator_db_url, ledger_urls, drained=True).status == "PASS"
    assert verify_all_ledgers()["status"] == "PASS"
