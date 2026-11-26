"""Tests for Stage 6 deterministic explainable recovery diagnostics."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from ledgerguard.config import settings
from ledgerguard.coordinator.directory_service import provision_account, register_customer
from ledgerguard.coordinator.failpoints import CrashAfterCommitError, FailpointManager
from ledgerguard.coordinator.transfer_coordinator import submit_coordinator_transfer
from ledgerguard.domain.money import AmountPaise
from ledgerguard.participant.posting_service import simulate_funding
from ledgerguard.recovery_explain import (
    RecoveryDiagnosticInput,
    explain_transfer_from_db,
    explain_transfer_recovery,
)
from ledgerguard.worker.orchestrator import recover_pending_transfers


def test_explain_all_valid_and_contradictory_states() -> None:
    # COMMITTING awaiting source confirm
    e1 = explain_transfer_recovery(
        RecoveryDiagnosticInput(
            transfer_id="tx-1",
            transfer_state="COMMITTING",
            decision="COMMIT",
            source_confirmed=False,
        )
    )
    assert e1.classification == "COMMITTED_AWAITING_SOURCE_CONFIRM"
    assert "cannot be cancelled" in e1.safety_implication

    # COMMITTING awaiting dest confirm
    e2 = explain_transfer_recovery(
        RecoveryDiagnosticInput(
            transfer_id="tx-2",
            transfer_state="COMMITTING",
            decision="COMMIT",
            source_confirmed=True,
            destination_confirmed=False,
        )
    )
    assert e2.classification == "COMMITTED_AWAITING_DEST_CONFIRM"
    assert "ledger-2" in e2.next_action

    # Partial reachability
    e3 = explain_transfer_recovery(
        RecoveryDiagnosticInput(
            transfer_id="tx-3",
            transfer_state="COMMITTING",
            decision="COMMIT",
            reachable_databases={"coordinator": True, "ledger-1": True, "ledger-2": False},
        )
    )
    assert e3.classification == "PARTIAL_REACHABILITY_BLOCKED"
    assert e3.blocking_dependency == "ledger-2"

    # Contradictory state: CANCEL decision with SETTLED state
    e4 = explain_transfer_recovery(
        RecoveryDiagnosticInput(
            transfer_id="tx-4",
            transfer_state="SETTLED",
            decision="CANCEL",
        )
    )
    assert e4.classification == "CONTRADICTORY_STATE_DETECTED"
    assert e4.operator_action_required is True

    # Unknown state combination -> UNCLASSIFIED_STATE
    e5 = explain_transfer_recovery(
        RecoveryDiagnosticInput(
            transfer_id="tx-5",
            transfer_state="MYSTERY_STATE",
            decision=None,
        )
    )
    assert e5.classification == "UNCLASSIFIED_STATE"
    assert e5.operator_action_required is True


@pytest.mark.integration
def test_explain_commit_after_crash_signature_scenario() -> None:
    ledger_urls = {"ledger-1": settings.ledger1_db_url, "ledger-2": settings.ledger2_db_url}
    c1 = register_customer(settings.coordinator_db_url, "Exp Alice", f"exp-a-{uuid4()}@test.local")
    c2 = register_customer(settings.coordinator_db_url, "Exp Bob", f"exp-b-{uuid4()}@test.local")
    a1 = provision_account(settings.coordinator_db_url, ledger_urls, UUID(str(c1["customer_id"])), "ledger-1")
    a2 = provision_account(settings.coordinator_db_url, ledger_urls, UUID(str(c2["customer_id"])), "ledger-2")
    src_id = UUID(str(a1["account_id"]))
    dst_id = UUID(str(a2["account_id"]))
    simulate_funding(settings.ledger1_db_url, src_id, AmountPaise(50_000))

    tx_id = uuid4()
    fp = FailpointManager()
    fp.set_failpoint("FAIL_AFTER_COMMIT_BEFORE_SOURCE_CONFIRM", tx_id)

    with pytest.raises(CrashAfterCommitError):
        submit_coordinator_transfer(
            settings.coordinator_db_url,
            ledger_urls,
            idempotency_key=f"exp-idem-{tx_id}",
            source_account_id=src_id,
            destination_account_id=dst_id,
            amount=AmountPaise(10_000),
            transfer_id=tx_id,
            failpoint_mgr=fp,
        )

    during_crash = explain_transfer_from_db(settings.coordinator_db_url, ledger_urls, tx_id)
    assert during_crash.classification == "COMMITTED_AWAITING_SOURCE_CONFIRM"
    assert during_crash.current_state == "COMMITTING"
    assert "source_hold=ACTIVE" in during_crash.evidence_references

    recover_pending_transfers(settings.coordinator_db_url, ledger_urls, transfer_id=tx_id)
    after_recovery = explain_transfer_from_db(settings.coordinator_db_url, ledger_urls, tx_id)
    assert after_recovery.classification == "SETTLED_COMPLETE"
