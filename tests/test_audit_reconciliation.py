"""Stage 5 tests for multi-database reconciliation, corrupted fixture detection, and drained invariants."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from ledgerguard.coordinator.directory_service import provision_account, register_customer
from ledgerguard.coordinator.reconciliation import (
    run_cross_ledger_reconciliation,
)
from ledgerguard.coordinator.transfer_coordinator import submit_coordinator_transfer
from ledgerguard.db.pool import get_db_connection
from ledgerguard.domain.money import AmountPaise
from ledgerguard.participant.account_service import create_ledger_account
from ledgerguard.participant.posting_service import simulate_funding

COORD_DB_URL = "postgresql://ledgerguard_app:ledgerguard_app_secret@localhost:5442/coordinator_db"
LEDGER1_DB_URL = "postgresql://ledgerguard_app:ledgerguard_app_secret@localhost:5443/ledger1_db"
LEDGER2_DB_URL = "postgresql://ledgerguard_app:ledgerguard_app_secret@localhost:5444/ledger2_db"

COORD_ADMIN_DB_URL = "postgresql://ledgerguard_admin:ledgerguard_admin_secret@localhost:5442/coordinator_db"
LEDGER1_ADMIN_DB_URL = "postgresql://ledgerguard_admin:ledgerguard_admin_secret@localhost:5443/ledger1_db"

LEDGER_URLS = {
    "ledger-1": LEDGER1_DB_URL,
    "ledger-2": LEDGER2_DB_URL,
}


@pytest.fixture
def funded_pair():
    c1 = register_customer(COORD_DB_URL, "Audit Alice", f"alice-audit-{uuid4()}@test.com")
    c2 = register_customer(COORD_DB_URL, "Audit Bob", f"bob-audit-{uuid4()}@test.com")

    alice_routing = provision_account(
        COORD_DB_URL, LEDGER_URLS, UUID(str(c1["customer_id"])), "ledger-1", currency="INR"
    )
    bob_routing = provision_account(
        COORD_DB_URL, LEDGER_URLS, UUID(str(c2["customer_id"])), "ledger-2", currency="INR"
    )

    alice_id = UUID(str(alice_routing["account_id"]))
    bob_id = UUID(str(bob_routing["account_id"]))

    simulate_funding(LEDGER1_DB_URL, alice_id, AmountPaise(50_000))
    return alice_id, bob_id


@pytest.mark.integration
def test_cross_ledger_reconciliation_connectivity_and_coverage(funded_pair):
    """Reconciliation over accessible instances reports full coverage and checks."""
    alice_id, bob_id = funded_pair

    # Complete a valid transfer
    submit_coordinator_transfer(
        COORD_DB_URL,
        LEDGER_URLS,
        idempotency_key=f"audit-tx-{uuid4()}",
        source_account_id=alice_id,
        destination_account_id=bob_id,
        amount=AmountPaise(10_000),
    )

    report = run_cross_ledger_reconciliation(COORD_DB_URL, LEDGER_URLS, drained=False)
    assert report.coverage == "FULL"
    assert "coordinator" in report.reachable_ledgers
    assert "ledger-1" in report.reachable_ledgers
    assert "ledger-2" in report.reachable_ledgers
    assert len(report.unreachable_ledgers) == 0


@pytest.mark.integration
def test_partial_reachability_reports_incomplete_not_pass():
    """Rule: Unreachable participant yields incomplete coverage, never global PASS."""
    bogus_ledgers = {
        "ledger-1": LEDGER1_DB_URL,
        "ledger-2": "postgresql://ledgerguard_app:wrong@localhost:5499/nonexistent",
    }

    report = run_cross_ledger_reconciliation(COORD_DB_URL, bogus_ledgers)
    assert report.status == "INCOMPLETE"
    assert report.coverage == "PARTIAL"
    assert "ledger-2" in report.unreachable_ledgers

    unreachable_findings = [f for f in report.findings if f.check_name == "UNREACHABLE_PARTICIPANT"]
    assert len(unreachable_findings) == 1
    assert unreachable_findings[0].ledger_id == "ledger-2"


@pytest.mark.integration
def test_corrupted_hold_cache_detected():
    """Controlled corrupted fixture: tampered held_amount_minor must trigger HOLD_CACHE_MISMATCH."""
    acct = create_ledger_account(LEDGER1_DB_URL)

    # Use admin connection to deliberately corrupt the cache (simulating data corruption)
    with get_db_connection(LEDGER1_ADMIN_DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE account_balances
                SET held_amount_minor = 99999
                WHERE account_id = %s;
            """,
                (acct.account_id,),
            )
        conn.commit()

    report = run_cross_ledger_reconciliation(COORD_DB_URL, LEDGER_URLS)
    assert report.status == "FAIL"

    hold_mismatches = [
        f for f in report.findings
        if f.check_name == "HOLD_CACHE_MISMATCH" and f.resource_id == str(acct.account_id)
    ]
    assert len(hold_mismatches) == 1
    assert "99999" in hold_mismatches[0].details

    # Clean up corrupted fixture
    with get_db_connection(LEDGER1_ADMIN_DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE account_balances SET held_amount_minor = 0 WHERE account_id = %s;",
                (acct.account_id,),
            )
        conn.commit()


@pytest.mark.integration
def test_stopped_and_drained_audit_detects_undrained_transfers():
    """Drained audit fails if unresolved in-flight transfers exist."""
    t_id = uuid4()
    with get_db_connection(COORD_DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO transfers (
                    transfer_id, idempotency_key, source_account_id, destination_account_id,
                    amount_minor, currency, transfer_type, state, source_ledger_id, destination_ledger_id
                ) VALUES (%s, %s, %s, %s, 1000, 'INR', 'CROSS_LEDGER', 'COMMITTING', 'ledger-1', 'ledger-2');
            """,
                (t_id, f"undrained-{t_id}", uuid4(), uuid4()),
            )
        conn.commit()

    report = run_cross_ledger_reconciliation(COORD_DB_URL, LEDGER_URLS, drained=True)
    assert report.status == "FAIL"

    undrained_findings = [f for f in report.findings if f.check_name == "UNDRAINED_TRANSFERS"]
    assert len(undrained_findings) == 1

    # Cleanup test row
    with get_db_connection(COORD_ADMIN_DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM transfers WHERE transfer_id = %s;", (t_id,))
        conn.commit()
