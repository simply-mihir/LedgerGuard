"""Tests for Stage 5 end-to-end OpenTelemetry tracing and sensitive-data redaction."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from ledgerguard.config import settings
from ledgerguard.coordinator.directory_service import provision_account, register_customer
from ledgerguard.coordinator.failpoints import CrashAfterCommitError, FailpointManager
from ledgerguard.coordinator.transfer_coordinator import submit_coordinator_transfer
from ledgerguard.domain.money import AmountPaise
from ledgerguard.observability import (
    amount_bucket,
    configure_tracing,
    get_trace_waterfall_for_transfer,
    sanitize_attributes,
)
from ledgerguard.participant.posting_service import simulate_funding
from ledgerguard.worker.orchestrator import recover_pending_transfers


def test_sensitive_attributes_stripped_and_amount_bucketed() -> None:
    clean = sanitize_attributes(
        {
            "transfer.id": "tx-123",
            "password": "secret-password",
            "csrf_token": "tok",
            "totp_secret": "JBSWY3DPEHPK3PXP",
            "session_token": "raw-session",
            "amount.bucket": amount_bucket(50_000),
        }
    )
    assert "transfer.id" in clean
    assert clean["amount.bucket"] == "100_to_999_INR"
    assert "password" not in clean
    assert "csrf_token" not in clean
    assert "totp_secret" not in clean
    assert "session_token" not in clean


@pytest.mark.integration
def test_end_to_end_trace_spans_transfer_and_forward_recovery() -> None:
    exporter = configure_tracing("memory")
    assert exporter is not None
    exporter.clear()

    ledger_urls = {"ledger-1": settings.ledger1_db_url, "ledger-2": settings.ledger2_db_url}
    c1 = register_customer(settings.coordinator_db_url, "Trace Alice", f"trace-a-{uuid4()}@test.local")
    c2 = register_customer(settings.coordinator_db_url, "Trace Bob", f"trace-b-{uuid4()}@test.local")
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
            idempotency_key=f"trace-idem-{tx_id}",
            source_account_id=src_id,
            destination_account_id=dst_id,
            amount=AmountPaise(10_000),
            transfer_id=tx_id,
            failpoint_mgr=fp,
        )

    recover_pending_transfers(settings.coordinator_db_url, ledger_urls, transfer_id=tx_id)

    waterfall = get_trace_waterfall_for_transfer(str(tx_id))
    span_names = [s["name"] for s in waterfall["spans"]]
    assert "coordinator.submit_transfer" in span_names
    assert "idempotency.lookup" in span_names
    assert "tcc.source_prepare" in span_names
    assert "recovery.retry_transfer" in span_names
    assert waterfall["metrics"]["recovery_span_count"] >= 1
    assert waterfall["metrics"]["error_span_count"] >= 1
