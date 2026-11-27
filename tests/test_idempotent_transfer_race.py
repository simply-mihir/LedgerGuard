"""One idempotency key must settle exactly one transfer, even when submitted concurrently.

Regression for a double spend: transfers.idempotency_key had no unique constraint or index and
api_idempotency is written only after settlement, so N concurrent requests with one key each
created and settled their own transfer (N times the debit).
"""

from __future__ import annotations

import threading
from uuid import UUID, uuid4

import psycopg
import pytest

from ledgerguard.audit import verify_all_ledgers
from ledgerguard.config import settings
from ledgerguard.coordinator.directory_service import provision_account, register_customer
from ledgerguard.coordinator.idempotent_transfer import insert_or_adopt_transfer
from ledgerguard.coordinator.reconciliation import run_cross_ledger_reconciliation
from ledgerguard.coordinator.transfer_coordinator import submit_coordinator_transfer
from ledgerguard.domain.idempotency import IdempotencyConflictError
from ledgerguard.domain.money import AmountPaise
from ledgerguard.participant.account_service import get_account_balance
from ledgerguard.participant.posting_service import simulate_funding

COORD = settings.coordinator_db_url
LEDGERS = {"ledger-1": settings.ledger1_db_url, "ledger-2": settings.ledger2_db_url}


def _purge_fixture_transfers(transfer_ids: list[UUID]) -> None:
    """Remove the fabricated-account transfers a test inserted, so they cannot linger as 'open'
    work for the recovery sweep and the drained-audit tests (the claims row cascades)."""
    with psycopg.connect(settings.coordinator_admin_db_url) as conn:
        conn.execute("DELETE FROM outbox_events WHERE aggregate_id = ANY(%s)",
                     ([str(t) for t in transfer_ids],))
        conn.execute("DELETE FROM workflow_events WHERE transfer_id = ANY(%s)", (transfer_ids,))
        conn.execute("DELETE FROM transfer_decisions WHERE transfer_id = ANY(%s)", (transfer_ids,))
        conn.execute("DELETE FROM transfers WHERE transfer_id = ANY(%s)", (transfer_ids,))
        conn.commit()


def _pair(funded: int = 10_000) -> tuple[UUID, UUID]:
    c1 = register_customer(COORD, "Race A", f"race-a-{uuid4()}@test.local")
    c2 = register_customer(COORD, "Race B", f"race-b-{uuid4()}@test.local")
    a = UUID(str(provision_account(COORD, LEDGERS, UUID(str(c1["customer_id"])), "ledger-1")["account_id"]))
    b = UUID(str(provision_account(COORD, LEDGERS, UUID(str(c2["customer_id"])), "ledger-2")["account_id"]))
    simulate_funding(settings.ledger1_db_url, a, AmountPaise(funded))
    return a, b


@pytest.mark.concurrency
@pytest.mark.integration
def test_concurrent_requests_with_one_key_settle_exactly_one_transfer() -> None:
    a, b = _pair()
    key = f"race-{uuid4()}"
    workers = 8
    barrier = threading.Barrier(workers)
    results: list[dict] = []
    errors: list[BaseException] = []

    def go() -> None:
        barrier.wait(timeout=10)
        try:
            results.append(submit_coordinator_transfer(COORD, LEDGERS, key, a, b, AmountPaise(1_000)))
        except BaseException as exc:  # noqa: BLE001 - asserted empty below
            errors.append(exc)

    threads = [threading.Thread(target=go) for _ in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(90)

    assert errors == []
    assert len(results) == workers
    assert {r["transfer_id"] for r in results} == {results[0]["transfer_id"]}  # one transfer
    assert {r["status"] for r in results} == {"SETTLED"}

    with psycopg.connect(settings.coordinator_admin_db_url) as conn:
        rows = conn.execute("SELECT state FROM transfers WHERE idempotency_key = %s", (key,)).fetchall()
        claims = conn.execute(
            "SELECT count(*) FROM transfer_idempotency_claims WHERE idempotency_key = %s", (key,)
        ).fetchone()
    assert rows == [("SETTLED",)]
    assert claims == (1,)
    assert get_account_balance(settings.ledger1_db_url, a).posted_balance_minor == 9_000  # debited once
    assert get_account_balance(settings.ledger2_db_url, b).posted_balance_minor == 1_000  # credited once
    recon = run_cross_ledger_reconciliation(COORD, LEDGERS, drained=False)
    assert recon.status == "PASS", recon.findings
    assert verify_all_ledgers()["status"] == "PASS"


@pytest.mark.integration
def test_sequential_replay_returns_the_same_receipt_without_a_second_debit() -> None:
    a, b = _pair()
    key = f"replay-{uuid4()}"
    first = submit_coordinator_transfer(COORD, LEDGERS, key, a, b, AmountPaise(2_000))
    again = submit_coordinator_transfer(COORD, LEDGERS, key, a, b, AmountPaise(2_000))
    assert again == first
    assert get_account_balance(settings.ledger1_db_url, a).posted_balance_minor == 8_000


@pytest.mark.integration
def test_same_key_with_a_different_payload_is_a_conflict_not_a_second_transfer() -> None:
    a, b = _pair()
    key = f"conflict-{uuid4()}"
    submit_coordinator_transfer(COORD, LEDGERS, key, a, b, AmountPaise(1_000))
    with pytest.raises(IdempotencyConflictError):
        submit_coordinator_transfer(COORD, LEDGERS, key, a, b, AmountPaise(1_500))
    assert get_account_balance(settings.ledger1_db_url, a).posted_balance_minor == 9_000


@pytest.mark.integration
def test_database_rejects_a_second_transfer_row_for_a_claimed_key() -> None:
    """Enforced in the database, so even code that bypasses the helper cannot duplicate a key."""
    key = f"db-{uuid4()}"
    first = uuid4()
    args = (first, key, uuid4(), uuid4(), 100, "INR", "CROSS_LEDGER", "ledger-1", "ledger-2")
    sql = ("INSERT INTO transfers (transfer_id, idempotency_key, source_account_id, "
           "destination_account_id, amount_minor, currency, transfer_type, state, "
           "source_ledger_id, destination_ledger_id) "
           "VALUES (%s,%s,%s,%s,%s,%s,%s,'SETTLED',%s,%s)")
    try:
        with psycopg.connect(settings.coordinator_admin_db_url) as conn:
            conn.execute(sql, args)
            conn.commit()
            with pytest.raises(psycopg.errors.UniqueViolation):
                conn.execute(sql, (uuid4(),) + args[1:])
            conn.rollback()
    finally:
        _purge_fixture_transfers([first])


@pytest.mark.integration
def test_helper_dispositions_and_payload_conflict() -> None:
    key = f"disp-{uuid4()}"
    tid = uuid4()
    kw = {
        "source_account_id": uuid4(), "destination_account_id": uuid4(), "amount_minor": 500,
        "currency": "INR", "transfer_type": "CROSS_LEDGER",
        "source_ledger_id": "ledger-1", "destination_ledger_id": "ledger-2",
    }
    try:
        _, d1 = insert_or_adopt_transfer(COORD, transfer_id=tid, idempotency_key=key, **kw)  # type: ignore[arg-type]
        _, d2 = insert_or_adopt_transfer(COORD, transfer_id=tid, idempotency_key=key, **kw)  # type: ignore[arg-type]
        _, d3 = insert_or_adopt_transfer(COORD, transfer_id=uuid4(), idempotency_key=key, **kw)  # type: ignore[arg-type]
        assert (d1, d2, d3) == ("created", "same_id", "adopted")
        with pytest.raises(IdempotencyConflictError):
            insert_or_adopt_transfer(COORD, transfer_id=uuid4(), idempotency_key=key,
                                     **{**kw, "amount_minor": 501})  # type: ignore[arg-type]
    finally:
        _purge_fixture_transfers([tid])
