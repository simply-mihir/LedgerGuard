"""Distributed TCC failure-matrix and recovery tests across independent PostgreSQL instances.

Tests:
1. End-to-end happy path cross-ledger transfer and balanced inter-ledger clearing.
2. Insufficient funds rejection on source prepare.
3. Destination rejection triggers automatic cancellation and release of source hold.
4. Lost source-prepare reply: retry recovers existing hold without double hold.
5. Crash after COMMIT: forward recovery guarantees completion; no rollback/refund.
6. Crash between source confirm and destination confirm: forward recovery settles destination.
7. Lost destination-confirm reply: deduplicated; no duplicate credit.
8. Freeze after acceptance: accepted obligation completes internally; new prepare rejects.
9. Account closure: blocked while unresolved obligations or active holds exist.
10. Cancel before prepare: durable tombstone rejects delayed prepare.
11. Workflow timeline distinct settlement events and zero duplicate on retry.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest

from ledgerguard.coordinator.directory_service import provision_account, register_customer
from ledgerguard.coordinator.failpoints import (
    CrashAfterCommitError,
    CrashAfterSourceConfirmError,
    FailpointManager,
    TransportTimeoutError,
)
from ledgerguard.coordinator.transfer_coordinator import submit_coordinator_transfer
from ledgerguard.db.pool import get_db_connection
from ledgerguard.domain.idempotency import IdempotencyConflictError
from ledgerguard.domain.models import AccountStatus
from ledgerguard.domain.money import AmountPaise
from ledgerguard.participant.account_service import (
    AccountLifecycleError,
    create_ledger_account,
    get_account_balance,
    set_account_status,
)
from ledgerguard.participant.posting_service import simulate_funding
from ledgerguard.participant.workflow_handler import (
    handle_destination_prepare,
    handle_participant_cancel,
    handle_source_prepare,
)
from ledgerguard.worker.orchestrator import execute_two_phase_commit, recover_pending_transfers

COORD_DB_URL = "postgresql://ledgerguard_app:ledgerguard_app_secret@localhost:5442/coordinator_db"
LEDGER1_DB_URL = "postgresql://ledgerguard_app:ledgerguard_app_secret@localhost:5443/ledger1_db"
LEDGER2_DB_URL = "postgresql://ledgerguard_app:ledgerguard_app_secret@localhost:5444/ledger2_db"

LEDGER_URLS = {
    "ledger-1": LEDGER1_DB_URL,
    "ledger-2": LEDGER2_DB_URL,
}
CLEARING_ACCOUNT_ID = UUID("00000000-0000-0000-0000-000000000002")


@pytest.fixture
def clean_accounts():
    """Setup customers and funded accounts on ledger-1 and ledger-2."""
    c1 = register_customer(COORD_DB_URL, "Alice Coordinator", f"alice-{uuid4()}@test.com")
    c2 = register_customer(COORD_DB_URL, "Bob Coordinator", f"bob-{uuid4()}@test.com")

    alice_routing = provision_account(
        COORD_DB_URL, LEDGER_URLS, UUID(str(c1["customer_id"])), "ledger-1", currency="INR"
    )
    bob_routing = provision_account(
        COORD_DB_URL, LEDGER_URLS, UUID(str(c2["customer_id"])), "ledger-2", currency="INR"
    )

    alice_id = UUID(str(alice_routing["account_id"]))
    bob_id = UUID(str(bob_routing["account_id"]))

    # Fund Alice with 100_000 paise (1,000 INR)
    simulate_funding(LEDGER1_DB_URL, alice_id, AmountPaise(100_000))

    return alice_id, bob_id


@pytest.mark.integration
def test_end_to_end_cross_ledger_transfer(clean_accounts):
    """Happy path: Alice (L1) -> Bob (L2) TCC completes and clearing accounts balance."""
    alice_id, bob_id = clean_accounts
    amt = AmountPaise(25_000)

    l1_clearing_before = get_account_balance(LEDGER1_DB_URL, CLEARING_ACCOUNT_ID)
    l2_clearing_before = get_account_balance(LEDGER2_DB_URL, CLEARING_ACCOUNT_ID)

    res = submit_coordinator_transfer(
        COORD_DB_URL,
        LEDGER_URLS,
        idempotency_key=f"tx-{uuid4()}",
        source_account_id=alice_id,
        destination_account_id=bob_id,
        amount=amt,
    )

    assert res["status"] == "SETTLED"
    assert res["transfer_type"] == "CROSS_LEDGER"

    # Balances
    alice_bal = get_account_balance(LEDGER1_DB_URL, alice_id)
    bob_bal = get_account_balance(LEDGER2_DB_URL, bob_id)
    assert alice_bal.posted_balance_minor == 75_000
    assert alice_bal.held_amount_minor == 0
    assert bob_bal.posted_balance_minor == 25_000

    # Cross-ledger clearing check:
    # L1 clearing (CONTROL) was credited 25_000
    # L2 clearing (CONTROL) was debited 25_000
    l1_clearing_after = get_account_balance(LEDGER1_DB_URL, CLEARING_ACCOUNT_ID)
    l2_clearing_after = get_account_balance(LEDGER2_DB_URL, CLEARING_ACCOUNT_ID)
    delta_l1 = l1_clearing_after.posted_balance_minor - l1_clearing_before.posted_balance_minor
    delta_l2 = l2_clearing_after.posted_balance_minor - l2_clearing_before.posted_balance_minor
    assert delta_l1 + delta_l2 == 0


@pytest.mark.integration
def test_insufficient_funds_source_prepare_rejects(clean_accounts):
    """Source prepare fails when amount exceeds available balance; transfer cancels."""
    alice_id, bob_id = clean_accounts
    amt = AmountPaise(500_000)  # Alice has only 100_000

    res = submit_coordinator_transfer(
        COORD_DB_URL,
        LEDGER_URLS,
        idempotency_key=f"tx-{uuid4()}",
        source_account_id=alice_id,
        destination_account_id=bob_id,
        amount=amt,
    )

    assert res["status"] == "CANCELLED"
    assert "Insufficient available funds" in res["reason"]

    alice_bal = get_account_balance(LEDGER1_DB_URL, alice_id)
    assert alice_bal.posted_balance_minor == 100_000
    assert alice_bal.held_amount_minor == 0


@pytest.mark.integration
def test_destination_freeze_triggers_cancellation_and_releases_hold(clean_accounts):
    """If destination prepare fails (e.g. FROZEN), source hold is automatically released."""
    alice_id, bob_id = clean_accounts
    amt = AmountPaise(30_000)

    # Freeze Bob
    set_account_status(LEDGER2_DB_URL, bob_id, AccountStatus.FROZEN, reason="Compliance test")

    res = submit_coordinator_transfer(
        COORD_DB_URL,
        LEDGER_URLS,
        idempotency_key=f"tx-{uuid4()}",
        source_account_id=alice_id,
        destination_account_id=bob_id,
        amount=amt,
    )

    assert res["status"] == "CANCELLED"
    assert "FROZEN" in res["reason"] or "not ACTIVE" in res["reason"]

    # Source hold MUST be released!
    alice_bal = get_account_balance(LEDGER1_DB_URL, alice_id)
    assert alice_bal.posted_balance_minor == 100_000
    assert alice_bal.held_amount_minor == 0
    assert alice_bal.available_balance_minor == 100_000


@pytest.mark.integration
def test_lost_source_prepare_reply_idempotent_retry(clean_accounts):
    """Crash/timeout after source prepare commits: retry recovers existing hold without duplicating."""
    alice_id, bob_id = clean_accounts
    amt = AmountPaise(15_000)
    key = f"tx-{uuid4()}"
    t_id = uuid4()

    fp = FailpointManager()
    fp.set_failpoint("FAIL_AFTER_SOURCE_PREPARE_REPLY", t_id)

    # First attempt fails with TransportTimeoutError
    with pytest.raises(TransportTimeoutError):
        submit_coordinator_transfer(
            COORD_DB_URL,
            LEDGER_URLS,
            idempotency_key=key,
            source_account_id=alice_id,
            destination_account_id=bob_id,
            amount=amt,
            transfer_id=t_id,
            failpoint_mgr=fp,
        )

    # Hold was created on Ledger 1
    alice_bal = get_account_balance(LEDGER1_DB_URL, alice_id)
    assert alice_bal.held_amount_minor == 15_000

    # Retry with identical key and transfer_id
    res = submit_coordinator_transfer(
        COORD_DB_URL,
        LEDGER_URLS,
        idempotency_key=key,
        source_account_id=alice_id,
        destination_account_id=bob_id,
        amount=amt,
        transfer_id=t_id,
        failpoint_mgr=fp,
    )

    assert res["status"] == "SETTLED"
    alice_bal_final = get_account_balance(LEDGER1_DB_URL, alice_id)
    assert alice_bal_final.posted_balance_minor == 85_000
    assert alice_bal_final.held_amount_minor == 0


@pytest.mark.integration
def test_crash_after_commit_recovers_forward(clean_accounts):
    """SIGNATURE SCENARIO: Crash after COMMIT decision must recover forward; never refund."""
    alice_id, bob_id = clean_accounts
    amt = AmountPaise(40_000)
    key = f"tx-{uuid4()}"
    t_id = uuid4()

    fp = FailpointManager()
    fp.set_failpoint("FAIL_AFTER_COMMIT_BEFORE_SOURCE_CONFIRM", t_id)

    with pytest.raises(CrashAfterCommitError):
        submit_coordinator_transfer(
            COORD_DB_URL,
            LEDGER_URLS,
            idempotency_key=key,
            source_account_id=alice_id,
            destination_account_id=bob_id,
            amount=amt,
            transfer_id=t_id,
            failpoint_mgr=fp,
        )

    # Invariants while interrupted:
    # 1. Decision is committed
    with get_db_connection(COORD_DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT decision FROM transfer_decisions WHERE transfer_id = %s;", (t_id,))
            dec_row = cur.fetchone()
            assert dec_row and dec_row["decision"] == "COMMIT"

    # 2. Source hold is still active
    alice_bal = get_account_balance(LEDGER1_DB_URL, alice_id)
    assert alice_bal.held_amount_minor == 40_000

    # Execute recovery
    recovered = recover_pending_transfers(COORD_DB_URL, LEDGER_URLS)
    assert any(r["transfer_id"] == str(t_id) and r["status"] == "SETTLED" for r in recovered)

    # Invariants after forward recovery:
    alice_bal_after = get_account_balance(LEDGER1_DB_URL, alice_id)
    bob_bal_after = get_account_balance(LEDGER2_DB_URL, bob_id)
    assert alice_bal_after.posted_balance_minor == 60_000
    assert alice_bal_after.held_amount_minor == 0
    assert bob_bal_after.posted_balance_minor == 40_000


@pytest.mark.integration
def test_crash_between_source_confirm_and_dest_confirm(clean_accounts):
    """Crash after source settlement commits: recovery settles destination; zero residual holds."""
    alice_id, bob_id = clean_accounts
    amt = AmountPaise(20_000)
    key = f"tx-{uuid4()}"
    t_id = uuid4()

    fp = FailpointManager()
    fp.set_failpoint("FAIL_AFTER_SOURCE_CONFIRM_BEFORE_DEST_CONFIRM", t_id)

    with pytest.raises(CrashAfterSourceConfirmError):
        submit_coordinator_transfer(
            COORD_DB_URL,
            LEDGER_URLS,
            idempotency_key=key,
            source_account_id=alice_id,
            destination_account_id=bob_id,
            amount=amt,
            transfer_id=t_id,
            failpoint_mgr=fp,
        )

    # Source has already settled!
    alice_bal = get_account_balance(LEDGER1_DB_URL, alice_id)
    assert alice_bal.posted_balance_minor == 80_000
    assert alice_bal.held_amount_minor == 0

    # Bob has not yet received funds
    bob_bal = get_account_balance(LEDGER2_DB_URL, bob_id)
    assert bob_bal.posted_balance_minor == 0

    # Recovery resumes and completes destination settlement
    recover_pending_transfers(COORD_DB_URL, LEDGER_URLS)

    bob_bal_final = get_account_balance(LEDGER2_DB_URL, bob_id)
    assert bob_bal_final.posted_balance_minor == 20_000


@pytest.mark.integration
def test_lost_destination_confirm_reply(clean_accounts):
    """Lost reply after destination confirm committed: retry receives idempotent receipt."""
    alice_id, bob_id = clean_accounts
    amt = AmountPaise(10_000)
    key = f"tx-{uuid4()}"
    t_id = uuid4()

    fp = FailpointManager()
    fp.set_failpoint("FAIL_AFTER_DEST_CONFIRM_REPLY", t_id)

    with pytest.raises(TransportTimeoutError):
        submit_coordinator_transfer(
            COORD_DB_URL,
            LEDGER_URLS,
            idempotency_key=key,
            source_account_id=alice_id,
            destination_account_id=bob_id,
            amount=amt,
            transfer_id=t_id,
            failpoint_mgr=fp,
        )

    # Destination already received the 10_000
    bob_bal = get_account_balance(LEDGER2_DB_URL, bob_id)
    assert bob_bal.posted_balance_minor == 10_000

    # Recovery runs: must NOT credit Bob a second time!
    recover_pending_transfers(COORD_DB_URL, LEDGER_URLS)

    bob_bal_after = get_account_balance(LEDGER2_DB_URL, bob_id)
    assert bob_bal_after.posted_balance_minor == 10_000  # Exact single credit!


@pytest.mark.integration
def test_freeze_after_acceptance_allows_internal_finalization(clean_accounts):
    """Rule: Accepted obligations can finish internally despite subsequent freeze.

    New prepares must be rejected.
    """
    alice_id, bob_id = clean_accounts
    amt = 12_000
    t_id = uuid4()

    # 1. Source prepare
    p1 = handle_source_prepare(
        LEDGER1_DB_URL, f"sp-{t_id}", t_id, alice_id, bob_id, amt
    )
    assert p1["status"] == "PREPARED"

    # 2. Destination prepare (accepted)
    p2 = handle_destination_prepare(
        LEDGER2_DB_URL, f"dp-{t_id}", t_id, alice_id, bob_id, amt
    )
    assert p2["status"] == "PREPARED"

    # 3. Freeze destination account AFTER prepare accepted the obligation
    set_account_status(LEDGER2_DB_URL, bob_id, AccountStatus.FROZEN, reason="Investigating account")

    # 4. Confirmation must succeed internally!
    from ledgerguard.participant.workflow_handler import (
        handle_destination_confirm,
        handle_source_confirm,
    )
    c1 = handle_source_confirm(LEDGER1_DB_URL, f"sc-{t_id}", t_id)
    assert c1["status"] == "CONFIRMED"

    c2 = handle_destination_confirm(LEDGER2_DB_URL, f"dc-{t_id}", t_id)
    assert c2["status"] == "CONFIRMED"

    # Bob got credited despite being frozen
    bob_bal = get_account_balance(LEDGER2_DB_URL, bob_id)
    assert bob_bal.posted_balance_minor == amt
    assert bob_bal.status == AccountStatus.FROZEN

    # 5. But a NEW prepare for frozen Bob must be rejected!
    new_tid = uuid4()
    p_new = handle_destination_prepare(
        LEDGER2_DB_URL, f"dp-{new_tid}", new_tid, alice_id, bob_id, 5000
    )
    assert p_new["status"] == "REJECTED"


@pytest.mark.integration
def test_account_closure_blocked_by_unresolved_obligations():
    """Rule: Closure is blocked while unresolved incoming/outgoing obligations or active holds exist."""
    # Create empty accounts on Ledger 1 and Ledger 2
    c = register_customer(COORD_DB_URL, "Closure Test", f"closure-{uuid4()}@test.com")
    cust_id = UUID(str(c["customer_id"]))
    acct1 = create_ledger_account(LEDGER1_DB_URL, customer_id=cust_id)
    acct2 = create_ledger_account(LEDGER2_DB_URL, customer_id=cust_id)

    t_id = uuid4()

    # Destination prepare registers an incoming intent in PREPARED state
    handle_destination_prepare(
        LEDGER2_DB_URL, f"dp-{t_id}", t_id, acct1.account_id, acct2.account_id, 5000
    )

    # Attempting to close acct2 (destination) must fail due to unresolved transfer obligations
    with pytest.raises(AccountLifecycleError) as exc_info:
        set_account_status(LEDGER2_DB_URL, acct2.account_id, AccountStatus.CLOSED)

    assert "unresolved transfer obligations" in str(exc_info.value).lower()

    # Cancel the obligation
    handle_participant_cancel(LEDGER2_DB_URL, f"cancel-{t_id}", t_id, "Test cleanup")

    # Now closure succeeds!
    closed_acct = set_account_status(LEDGER2_DB_URL, acct2.account_id, AccountStatus.CLOSED)
    assert closed_acct.status == AccountStatus.CLOSED


@pytest.mark.integration
def test_cancel_before_prepare_creates_tombstone_and_rejects_delayed_prepare(clean_accounts):
    """Network message reordering: CANCEL arrives before PREPARE.

    Tombstone is created, delayed prepare rejects, and no funds are locked.
    """
    alice_id, bob_id = clean_accounts
    amt = 15_000
    t_id = uuid4()

    # Cancel arrives first
    c_res = handle_participant_cancel(
        LEDGER1_DB_URL, f"cancel-{t_id}", t_id, "Coordinator aborted early"
    )
    assert c_res["status"] == "CANCELLED"

    # Delayed source prepare arrives later
    p_res = handle_source_prepare(
        LEDGER1_DB_URL, f"sp-{t_id}", t_id, alice_id, bob_id, amt
    )
    assert p_res["status"] == "REJECTED"
    assert "tombstone" in p_res["reason"].lower()

    # Zero holds created on Alice's account
    alice_bal = get_account_balance(LEDGER1_DB_URL, alice_id)
    assert alice_bal.held_amount_minor == 0
    assert alice_bal.available_balance_minor == 100_000


@pytest.mark.integration
def test_distributed_transfer_idempotent_retry_after_settlement(clean_accounts):
    """External idempotency: Retrying with identical key returns settled response without duplicate financial effects.

    Retrying with identical key but altered payload raises IdempotencyConflictError.
    """
    alice_id, bob_id = clean_accounts
    amt = AmountPaise(20_000)
    idem_key = f"tx-idem-{uuid4()}"

    # Initial transfer
    res1 = submit_coordinator_transfer(
        COORD_DB_URL,
        LEDGER_URLS,
        idempotency_key=idem_key,
        source_account_id=alice_id,
        destination_account_id=bob_id,
        amount=amt,
    )
    assert res1["status"] == "SETTLED"

    alice_bal_1 = get_account_balance(LEDGER1_DB_URL, alice_id)
    bob_bal_1 = get_account_balance(LEDGER2_DB_URL, bob_id)
    assert alice_bal_1.posted_balance_minor == 80_000
    assert bob_bal_1.posted_balance_minor == 20_000

    # 1. Retry with identical key and payload: returns original result without duplicate balance change
    res2 = submit_coordinator_transfer(
        COORD_DB_URL,
        LEDGER_URLS,
        idempotency_key=idem_key,
        source_account_id=alice_id,
        destination_account_id=bob_id,
        amount=amt,
    )
    assert res2["status"] == "SETTLED"
    assert res2["transfer_id"] == res1["transfer_id"]

    alice_bal_2 = get_account_balance(LEDGER1_DB_URL, alice_id)
    bob_bal_2 = get_account_balance(LEDGER2_DB_URL, bob_id)
    assert alice_bal_2.posted_balance_minor == 80_000
    assert bob_bal_2.posted_balance_minor == 20_000

    # 2. Retry with identical key but altered amount payload: raises IdempotencyConflictError
    with pytest.raises(IdempotencyConflictError):
        submit_coordinator_transfer(
            COORD_DB_URL,
            LEDGER_URLS,
            idempotency_key=idem_key,
            source_account_id=alice_id,
            destination_account_id=bob_id,
            amount=AmountPaise(30_000),
        )


@pytest.mark.integration
def test_workflow_timeline_distinct_settlement_and_no_duplicate_on_retry(clean_accounts):
    """Regression test: verify forward recovery and subsequent idempotency retries

    emit distinct participant settlement events (SOURCE_CONFIRMED, DESTINATION_CONFIRMED)
    and do not duplicate TRANSFER_SETTLED events.
    """
    from psycopg.rows import dict_row

    alice_id, bob_id = clean_accounts
    amt = AmountPaise(15_000)
    transfer_id = uuid4()
    idem_key = f"crash-timeline-{transfer_id}"

    fp = FailpointManager()
    fp.set_failpoint("FAIL_AFTER_COMMIT_BEFORE_SOURCE_CONFIRM", transfer_id)

    # 1. Initiate transfer and simulate coordinator crash right after COMMIT decision
    with pytest.raises(CrashAfterCommitError):
        submit_coordinator_transfer(
            COORD_DB_URL,
            LEDGER_URLS,
            idempotency_key=idem_key,
            source_account_id=alice_id,
            destination_account_id=bob_id,
            amount=amt,
            transfer_id=transfer_id,
            failpoint_mgr=fp,
        )

    # 2. Inspect intermediate workflow events before recovery
    with get_db_connection(COORD_DB_URL) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT event_type, details FROM workflow_events WHERE transfer_id = %s ORDER BY created_at ASC;",
                (transfer_id,),
            )
            pre_recovery_events = cur.fetchall()

    event_types_pre = [r["event_type"] for r in pre_recovery_events]
    assert "PHASE_PREPARE_STARTED" in event_types_pre
    assert "DECISION_COMMITTED" in event_types_pre
    assert "TRANSFER_SETTLED" not in event_types_pre

    # 3. Autonomous forward recovery settles the transfer
    recovered = recover_pending_transfers(COORD_DB_URL, LEDGER_URLS, transfer_id=transfer_id)
    assert any(r["transfer_id"] == str(transfer_id) and r["status"] == "SETTLED" for r in recovered)

    # 4. Check workflow events after recovery: SOURCE_CONFIRMED and DESTINATION_CONFIRMED exist
    with get_db_connection(COORD_DB_URL) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT event_type, details FROM workflow_events WHERE transfer_id = %s ORDER BY created_at ASC;",
                (transfer_id,),
            )
            post_recovery_events = cur.fetchall()

    event_types_post = [r["event_type"] for r in post_recovery_events]
    assert event_types_post.count("TRANSFER_SETTLED") == 1
    assert "SOURCE_CONFIRMED" in event_types_post
    assert "DESTINATION_CONFIRMED" in event_types_post

    # Verify participant metadata in settlement events
    sc_ev = next(r for r in post_recovery_events if r["event_type"] == "SOURCE_CONFIRMED")
    dc_ev = next(r for r in post_recovery_events if r["event_type"] == "DESTINATION_CONFIRMED")
    assert sc_ev["details"]["role"] == "source"
    assert sc_ev["details"]["ledger_id"] == "ledger-1"
    assert dc_ev["details"]["role"] == "destination"
    assert dc_ev["details"]["ledger_id"] == "ledger-2"

    # 5. Client retries transfer submission with original idempotency key
    retry_res = submit_coordinator_transfer(
        COORD_DB_URL,
        LEDGER_URLS,
        idempotency_key=idem_key,
        source_account_id=alice_id,
        destination_account_id=bob_id,
        amount=amt,
        transfer_id=transfer_id,
    )
    assert retry_res["status"] == "SETTLED"

    # 6. Verify zero duplicate TRANSFER_SETTLED events after client retry
    with get_db_connection(COORD_DB_URL) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT event_type FROM workflow_events WHERE transfer_id = %s ORDER BY created_at ASC;",
                (transfer_id,),
            )
            post_retry_events = cur.fetchall()

    retry_types = [r["event_type"] for r in post_retry_events]
    assert retry_types.count("TRANSFER_SETTLED") == 1, (
        f"Expected exactly 1 TRANSFER_SETTLED event, got {retry_types.count('TRANSFER_SETTLED')}: {retry_types}"
    )
    assert retry_types.count("SOURCE_CONFIRMED") == 1
    assert retry_types.count("DESTINATION_CONFIRMED") == 1


def test_concurrent_recovery_workflow_event_uniqueness(clean_accounts: tuple[UUID, UUID]) -> None:
    """Test 12: Concurrent recovery attempts enforce database-level event uniqueness and idempotent settlement."""
    from psycopg.rows import dict_row

    alice_id, bob_id = clean_accounts
    transfer_id = uuid4()
    idem_key = f"concurrent-tx-{transfer_id}"
    amt = AmountPaise(400_00)

    fp = FailpointManager()
    fp.set_failpoint("FAIL_AFTER_COMMIT_BEFORE_SOURCE_CONFIRM", transfer_id)
    with pytest.raises(CrashAfterCommitError):
        submit_coordinator_transfer(
            COORD_DB_URL,
            LEDGER_URLS,
            idempotency_key=idem_key,
            source_account_id=alice_id,
            destination_account_id=bob_id,
            amount=amt,
            transfer_id=transfer_id,
            failpoint_mgr=fp,
        )

    # 2. Run two simultaneous recovery workers on the same interrupted transfer
    with ThreadPoolExecutor(max_workers=2) as executor:
        fut1 = executor.submit(execute_two_phase_commit, COORD_DB_URL, transfer_id, LEDGER_URLS)
        fut2 = executor.submit(execute_two_phase_commit, COORD_DB_URL, transfer_id, LEDGER_URLS)
        res1 = fut1.result()
        res2 = fut2.result()

    assert res1["status"] == "SETTLED"
    assert res2["status"] == "SETTLED"

    # 3. Verify final transfer state in coordinator DB is SETTLED
    with get_db_connection(COORD_DB_URL) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT state FROM transfers WHERE transfer_id = %s;", (transfer_id,))
            t_row = cur.fetchone()
            assert t_row is not None
            assert t_row["state"] == "SETTLED"

            # 4. Verify exactly one event for each (transfer_id, event_type)
            cur.execute(
                "SELECT event_type, details FROM workflow_events WHERE transfer_id = %s ORDER BY created_at ASC;",
                (transfer_id,),
            )
            events = cur.fetchall()

    event_types = [e["event_type"] for e in events]
    assert len(event_types) == 6, f"Expected exactly 6 unique events, got {len(event_types)}: {event_types}"
    assert event_types.count("PHASE_PREPARE_STARTED") == 1
    assert event_types.count("DECISION_MADE") == 1
    assert event_types.count("DECISION_COMMITTED") == 1
    assert event_types.count("SOURCE_CONFIRMED") == 1
    assert event_types.count("DESTINATION_CONFIRMED") == 1
    assert event_types.count("TRANSFER_SETTLED") == 1

    # Verify event details metadata
    sc_ev = next(e for e in events if e["event_type"] == "SOURCE_CONFIRMED")
    dc_ev = next(e for e in events if e["event_type"] == "DESTINATION_CONFIRMED")
    assert sc_ev["details"]["role"] == "source"
    assert sc_ev["details"]["ledger_id"] == "ledger-1"
    assert dc_ev["details"]["role"] == "destination"
    assert dc_ev["details"]["ledger_id"] == "ledger-2"

    # 5. Verify participant financial effects remain strictly idempotent
    alice_bal = get_account_balance(LEDGER1_DB_URL, alice_id)
    bob_bal = get_account_balance(LEDGER2_DB_URL, bob_id)
    assert alice_bal.posted_balance_minor == 600_00
    assert alice_bal.held_amount_minor == 0
    assert alice_bal.available_balance_minor == 600_00
    assert bob_bal.posted_balance_minor == 400_00
    assert bob_bal.available_balance_minor == 400_00

    # Verify single journal entry on participants
    with get_db_connection(LEDGER1_DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM journal_headers WHERE transfer_id = %s;", (transfer_id,))
            res = cur.fetchone()
            assert res is not None and list(res.values())[0] == 1

    with get_db_connection(LEDGER2_DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM journal_headers WHERE transfer_id = %s;", (transfer_id,))
            res = cur.fetchone()
            assert res is not None and list(res.values())[0] == 1
