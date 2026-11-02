"""Stage 3 verification suite: Durable workflow primitives, outbox, inbox, holds, and tombstones."""

from uuid import uuid4

import pytest

from ledgerguard.config import settings
from ledgerguard.db.pool import get_db_connection
from ledgerguard.domain.money import AmountPaise
from ledgerguard.participant.account_service import (
    create_ledger_account,
    get_account_balance,
)
from ledgerguard.participant.posting_service import simulate_funding
from ledgerguard.participant.workflow_handler import (
    get_hold_status,
    get_intent_status,
    handle_destination_confirm,
    handle_destination_prepare,
    handle_participant_cancel,
    handle_source_confirm,
    handle_source_prepare,
)
from ledgerguard.worker.coordinator_service import (
    IncompatibleDecisionError,
    create_coordinator_transfer,
    record_durable_decision,
)
from ledgerguard.worker.outbox import (
    claim_pending_outbox_events,
    mark_outbox_delivered,
)

COORD_DB_URL = settings.coordinator_db_url
COORD_ADMIN_DB_URL = "postgresql://ledgerguard_admin:ledgerguard_admin_secret@localhost:5442/coordinator_db"
LEDGER1_DB_URL = settings.ledger1_db_url
LEDGER2_DB_URL = settings.ledger2_db_url


def _cleanup_coordinator_transfer(transfer_id):
    with get_db_connection(COORD_ADMIN_DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM outbox_events WHERE aggregate_id = %s;", (str(transfer_id),))
            cur.execute("DELETE FROM workflow_events WHERE transfer_id = %s;", (transfer_id,))
            cur.execute("DELETE FROM transfer_decisions WHERE transfer_id = %s;", (transfer_id,))
            cur.execute("DELETE FROM transfers WHERE transfer_id = %s;", (transfer_id,))
        conn.commit()


# ---------------------------------------------------------------------------
# 1. Coordinator Request Creation & Outbox Atomicity
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_coordinator_transfer_creation_and_outbox():
    """Verify transfer creation and outbox event commit together atomically."""
    transfer_id = uuid4()
    idem_key = f"coord-create-{uuid4()}"
    src_id = uuid4()
    dst_id = uuid4()

    try:
        res = create_coordinator_transfer(
            coord_db_url=COORD_DB_URL,
            transfer_id=transfer_id,
            idempotency_key=idem_key,
            source_account_id=src_id,
            destination_account_id=dst_id,
            source_ledger_id="ledger1",
            destination_ledger_id="ledger2",
            amount_minor=5000,
        )
        assert res["state"] == "ACCEPTED"
        assert res["amount_minor"] == 5000

        # Claim outbox events
        events = claim_pending_outbox_events(COORD_DB_URL, batch_size=10, aggregate_id=transfer_id)
        matching = [e for e in events if e["aggregate_id"] == str(transfer_id)]
        assert len(matching) == 1
        assert matching[0]["event_type"] == "DISPATCH_PREPARE"

        # Mark delivered
        mark_outbox_delivered(COORD_DB_URL, matching[0]["outbox_id"])
    finally:
        _cleanup_coordinator_transfer(transfer_id)


# ---------------------------------------------------------------------------
# 2. Mutually Exclusive Durable Coordinator Decisions (COMMIT vs CANCEL)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_mutually_exclusive_durable_decisions():
    """Verify COMMIT and CANCEL are strictly mutually exclusive and immutable."""
    transfer_id = uuid4()
    try:
        create_coordinator_transfer(
            coord_db_url=COORD_DB_URL,
            transfer_id=transfer_id,
            idempotency_key=f"decision-test-{uuid4()}",
            source_account_id=uuid4(),
            destination_account_id=uuid4(),
            source_ledger_id="ledger1",
            destination_ledger_id="ledger2",
            amount_minor=2000,
        )

        # 1. Record COMMIT decision
        dec = record_durable_decision(
            COORD_DB_URL, transfer_id, decision="COMMIT", reason="Both prepared"
        )
        assert dec == "COMMIT"

        # 2. Idempotent re-entry returns same decision
        dec_again = record_durable_decision(COORD_DB_URL, transfer_id, decision="COMMIT")
        assert dec_again == "COMMIT"

        # 3. Switching from COMMIT to CANCEL must be strictly rejected
        with pytest.raises(IncompatibleDecisionError, match="already COMMIT"):
            record_durable_decision(COORD_DB_URL, transfer_id, decision="CANCEL")
    finally:
        _cleanup_coordinator_transfer(transfer_id)


@pytest.mark.integration
def test_cancel_decision_immutability():
    """Verify CANCEL decision cannot be subsequently changed to COMMIT."""
    transfer_id = uuid4()
    try:
        create_coordinator_transfer(
            coord_db_url=COORD_DB_URL,
            transfer_id=transfer_id,
            idempotency_key=f"cancel-immut-{uuid4()}",
            source_account_id=uuid4(),
            destination_account_id=uuid4(),
            source_ledger_id="ledger1",
            destination_ledger_id="ledger2",
            amount_minor=1500,
        )

        dec = record_durable_decision(
            COORD_DB_URL, transfer_id, decision="CANCEL", reason="Destination rejected"
        )
        assert dec == "CANCEL"

        with pytest.raises(IncompatibleDecisionError, match="already CANCEL"):
            record_durable_decision(COORD_DB_URL, transfer_id, decision="COMMIT")
    finally:
        _cleanup_coordinator_transfer(transfer_id)


# ---------------------------------------------------------------------------
# 3. Source Participant Prepare & Hold Invariants
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_source_prepare_hold_and_idempotency():
    """Verify source prepare reserves funds, increases held amount, and dedups retries."""
    alice = create_ledger_account(LEDGER1_DB_URL)
    bob_id = uuid4()
    simulate_funding(LEDGER1_DB_URL, alice.account_id, AmountPaise(10000))

    transfer_id = uuid4()
    cmd_id = f"cmd-prep-{transfer_id}"

    # 1. First prepare
    res1 = handle_source_prepare(
        db_url=LEDGER1_DB_URL,
        command_id=cmd_id,
        transfer_id=transfer_id,
        source_account_id=alice.account_id,
        dest_account_id=bob_id,
        amount_minor=4000,
    )
    assert res1["status"] == "PREPARED"

    # Alice posted is 10000, held is 4000, available is 6000
    bal1 = get_account_balance(LEDGER1_DB_URL, alice.account_id)
    assert bal1.posted_balance_minor == 10000
    assert bal1.held_amount_minor == 4000
    assert bal1.available_balance_minor == 6000

    hold = get_hold_status(LEDGER1_DB_URL, transfer_id)
    assert hold is not None
    assert hold["status"] == "ACTIVE"
    assert hold["amount_minor"] == 4000

    # 2. Duplicate prepare command (retry)
    res2 = handle_source_prepare(
        db_url=LEDGER1_DB_URL,
        command_id=cmd_id,
        transfer_id=transfer_id,
        source_account_id=alice.account_id,
        dest_account_id=bob_id,
        amount_minor=4000,
    )
    assert res2["status"] == "PREPARED"

    # Held amount must NOT double
    bal2 = get_account_balance(LEDGER1_DB_URL, alice.account_id)
    assert bal2.held_amount_minor == 4000
    assert bal2.available_balance_minor == 6000


# ---------------------------------------------------------------------------
# 4. Cancellation Tombstone / Reordered Commands Protection
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_cancel_before_prepare_tombstone_rejects_delayed_prepare():
    """MANDATORY GATE: Cancellation arriving before prepare creates a tombstone.

    A subsequent delayed prepare must be rejected with no stranded holds or intents.
    """
    alice = create_ledger_account(LEDGER1_DB_URL)
    bob_id = uuid4()
    simulate_funding(LEDGER1_DB_URL, alice.account_id, AmountPaise(5000))

    transfer_id = uuid4()

    # 1. Cancel arrives first (e.g. timeout on coordinator side)
    cancel_res = handle_participant_cancel(
        db_url=LEDGER1_DB_URL,
        command_id=f"cmd-cancel-{transfer_id}",
        transfer_id=transfer_id,
    )
    assert cancel_res["status"] == "CANCELLED"

    intent = get_intent_status(LEDGER1_DB_URL, transfer_id)
    assert intent is not None
    assert intent["status"] == "CANCELLED"

    # 2. Delayed prepare arrives now
    prep_res = handle_source_prepare(
        db_url=LEDGER1_DB_URL,
        command_id=f"cmd-delayed-prep-{transfer_id}",
        transfer_id=transfer_id,
        source_account_id=alice.account_id,
        dest_account_id=bob_id,
        amount_minor=3000,
    )
    assert prep_res["status"] == "REJECTED"
    assert "tombstone" in prep_res["reason"].lower()

    # Alice balance must have NO residual hold
    bal = get_account_balance(LEDGER1_DB_URL, alice.account_id)
    assert bal.held_amount_minor == 0
    assert bal.available_balance_minor == 5000

    hold = get_hold_status(LEDGER1_DB_URL, transfer_id)
    assert hold is None


# ---------------------------------------------------------------------------
# 5. Full Two-Phase Flow: Prepare -> Source Confirm -> Dest Confirm
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_full_two_phase_prepare_and_confirm_flow():
    """Verify source hold reservation, source confirm consuming hold, and dest credit."""
    alice = create_ledger_account(LEDGER1_DB_URL)
    bob = create_ledger_account(LEDGER2_DB_URL)
    simulate_funding(LEDGER1_DB_URL, alice.account_id, AmountPaise(12000))

    transfer_id = uuid4()
    amt = 5000

    # 1. Source Prepare (Ledger 1)
    p1 = handle_source_prepare(
        LEDGER1_DB_URL, f"sp-{transfer_id}", transfer_id, alice.account_id, bob.account_id, amt
    )
    assert p1["status"] == "PREPARED"

    # 2. Destination Prepare (Ledger 2)
    p2 = handle_destination_prepare(
        LEDGER2_DB_URL, f"dp-{transfer_id}", transfer_id, alice.account_id, bob.account_id, amt
    )
    assert p2["status"] == "PREPARED"

    # 3. Source Confirm (Ledger 1)
    sc = handle_source_confirm(LEDGER1_DB_URL, f"sc-{transfer_id}", transfer_id)
    assert sc["status"] == "CONFIRMED"

    # Alice balance: posted decreased by 5000, held is 0
    alice_bal = get_account_balance(LEDGER1_DB_URL, alice.account_id)
    assert alice_bal.posted_balance_minor == 7000
    assert alice_bal.held_amount_minor == 0
    assert alice_bal.available_balance_minor == 7000

    # 4. Destination Confirm (Ledger 2)
    dc = handle_destination_confirm(LEDGER2_DB_URL, f"dc-{transfer_id}", transfer_id)
    assert dc["status"] == "CONFIRMED"

    # Bob balance: posted increased by 5000
    bob_bal = get_account_balance(LEDGER2_DB_URL, bob.account_id)
    assert bob_bal.posted_balance_minor == 5000
    assert bob_bal.available_balance_minor == 5000


# ---------------------------------------------------------------------------
# 6. CONFIRMED Cannot Become CANCELLED
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_confirmed_intent_cannot_be_cancelled():
    """Verify attempting to cancel a confirmed intent is strictly rejected."""
    alice = create_ledger_account(LEDGER1_DB_URL)
    bob = create_ledger_account(LEDGER2_DB_URL)
    simulate_funding(LEDGER1_DB_URL, alice.account_id, AmountPaise(8000))

    transfer_id = uuid4()
    amt = 3000

    handle_destination_prepare(
        LEDGER2_DB_URL, f"dp-{transfer_id}", transfer_id, alice.account_id, bob.account_id, amt
    )
    handle_source_prepare(
        LEDGER1_DB_URL, f"sp-{transfer_id}", transfer_id, alice.account_id, bob.account_id, amt
    )
    handle_source_confirm(LEDGER1_DB_URL, f"sc-{transfer_id}", transfer_id)

    # Attempt cancel after confirm must raise exception
    with pytest.raises(Exception, match="Cannot cancel CONFIRMED"):
        handle_participant_cancel(LEDGER1_DB_URL, f"cancel-post-confirm-{transfer_id}", transfer_id)

    # Confirm destination to preserve inter-ledger clearing conservation
    handle_destination_confirm(LEDGER2_DB_URL, f"dc-{transfer_id}", transfer_id)
