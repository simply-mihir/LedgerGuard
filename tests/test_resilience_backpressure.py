"""Tests for Stage 11 adaptive backpressure and per-participant circuit breaking."""

from __future__ import annotations

import time
from uuid import UUID, uuid4

import pytest

from ledgerguard.config import settings
from ledgerguard.coordinator.directory_service import provision_account, register_customer
from ledgerguard.coordinator.failpoints import CrashAfterCommitError, FailpointManager
from ledgerguard.coordinator.transfer_coordinator import submit_coordinator_transfer
from ledgerguard.domain.money import AmountPaise
from ledgerguard.participant.posting_service import simulate_funding
from ledgerguard.resilience import (
    BackpressureRejectedError,
    CircuitState,
    ParticipantResilienceController,
    ResiliencePolicy,
)
from ledgerguard.worker.orchestrator import recover_pending_transfers


@pytest.mark.integration
def test_circuit_breaker_open_half_open_closed_and_persistence() -> None:
    policy = ResiliencePolicy(
        failure_threshold=2,
        recovery_success_threshold=2,
        open_cooldown_seconds=0.1,
        half_open_probe_limit=2,
    )
    ctrl = ParticipantResilienceController(settings.coordinator_db_url, policy=policy)
    pid = f"test-part-{uuid4().hex[:6]}"
    ctrl.admit_new_transfer(pid)
    ctrl.release_slot(pid)

    assert ctrl.record_failure(pid, "timeout_1") == CircuitState.CLOSED
    assert ctrl.record_failure(pid, "timeout_2") == CircuitState.OPEN

    # Simulate process restart: new controller instance reads OPEN state from PostgreSQL
    ctrl2 = ParticipantResilienceController(settings.coordinator_db_url, policy=policy)
    with pytest.raises(BackpressureRejectedError):
        ctrl2.admit_new_transfer(pid)

    # Wait for cooldown -> HALF_OPEN probe -> CLOSED after 2 successes
    time.sleep(0.15)
    ctrl2.admit_new_transfer(pid)
    assert ctrl2.record_success(pid, 5.0) == CircuitState.HALF_OPEN
    assert ctrl2.record_success(pid, 4.0) == CircuitState.CLOSED


@pytest.mark.integration
def test_open_circuit_never_blocks_or_cancels_committed_forward_recovery() -> None:
    ledger_urls = {"ledger-1": settings.ledger1_db_url, "ledger-2": settings.ledger2_db_url}
    c1 = register_customer(settings.coordinator_db_url, "Res Alice", f"res-a-{uuid4()}@test.local")
    c2 = register_customer(settings.coordinator_db_url, "Res Bob", f"res-b-{uuid4()}@test.local")
    a1 = provision_account(settings.coordinator_db_url, ledger_urls, UUID(str(c1["customer_id"])), "ledger-1")
    a2 = provision_account(settings.coordinator_db_url, ledger_urls, UUID(str(c2["customer_id"])), "ledger-2")
    src_id = UUID(str(a1["account_id"]))
    dst_id = UUID(str(a2["account_id"]))
    simulate_funding(settings.ledger1_db_url, src_id, AmountPaise(20_000))

    tx_id = uuid4()
    fp = FailpointManager()
    fp.set_failpoint("FAIL_AFTER_COMMIT_BEFORE_SOURCE_CONFIRM", tx_id)
    with pytest.raises(CrashAfterCommitError):
        submit_coordinator_transfer(
            settings.coordinator_db_url,
            ledger_urls,
            idempotency_key=f"res-tx-{tx_id}",
            source_account_id=src_id,
            destination_account_id=dst_id,
            amount=AmountPaise(5_000),
            transfer_id=tx_id,
            failpoint_mgr=fp,
        )

    # Open circuit for ledger-2, then verify committed transfer still recovers forward!
    ctrl = ParticipantResilienceController(
        settings.coordinator_db_url, ResiliencePolicy(failure_threshold=1, open_cooldown_seconds=5.0)
    )
    assert ctrl.record_failure("ledger-2", "simulated_outage") == CircuitState.OPEN

    recovered = recover_pending_transfers(settings.coordinator_db_url, ledger_urls, transfer_id=tx_id)
    assert recovered[0]["status"] == "SETTLED"

    # Reset ledger-2 back to CLOSED for clean cluster state
    ctrl.record_success("ledger-2")
    with pytest.MonkeyPatch.context():
        pass
    from ledgerguard.db.pool import get_db_connection

    with get_db_connection(settings.coordinator_db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE participant_resilience_state SET circuit_state = 'CLOSED', failure_count = 0, next_probe_at = NULL WHERE participant_id = 'ledger-2';"
            )
        conn.commit()
