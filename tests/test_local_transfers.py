"""Stage 2 verification suite: Local transfers, idempotency, concurrent spending, and reversals."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from ledgerguard.api.app import app
from ledgerguard.config import settings
from ledgerguard.domain.idempotency import IdempotencyConflictError
from ledgerguard.domain.money import AmountPaise
from ledgerguard.participant.account_service import (
    create_ledger_account,
    get_account_balance,
)
from ledgerguard.participant.posting_service import (
    simulate_cash_out,
    simulate_funding,
)
from ledgerguard.participant.transfer_service import (
    ReversalConflictError,
    ReversalRejectedError,
    execute_local_transfer,
    execute_reversal,
    get_transfer_details,
)

DB_URL = settings.ledger1_db_url
client = TestClient(app)
AUTH_HEADERS = {"Authorization": f"Bearer {settings.api_bearer_token}"}


# ---------------------------------------------------------------------------
# 1. Local Transfers & State Consistency
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_local_transfer_happy_path():
    """Verify local wallet transfer transfers funds atomically and records SETTLED status."""
    alice = create_ledger_account(DB_URL)
    bob = create_ledger_account(DB_URL)

    # Fund Alice with 10,000 paise (INR 100.00)
    simulate_funding(DB_URL, alice.account_id, AmountPaise(10000))

    # Transfer 3,500 paise from Alice to Bob
    idem_key = f"xfer-happy-{uuid4()}"
    res = execute_local_transfer(
        DB_URL,
        idempotency_key=idem_key,
        source_account_id=alice.account_id,
        destination_account_id=bob.account_id,
        amount=AmountPaise(3500),
    )
    assert res["status"] == "SETTLED"
    assert res["amount_minor"] == 3500

    alice_bal = get_account_balance(DB_URL, alice.account_id)
    bob_bal = get_account_balance(DB_URL, bob.account_id)
    assert alice_bal.posted_balance_minor == 6500
    assert alice_bal.available_balance_minor == 6500
    assert bob_bal.posted_balance_minor == 3500
    assert bob_bal.available_balance_minor == 3500

    # Verify transfer details lookup
    details = get_transfer_details(DB_URL, res["transfer_id"])
    assert details["status"] == "SETTLED"
    assert details["is_reversed"] is False


# ---------------------------------------------------------------------------
# 2. Idempotency: Retries and Payload Fingerprint Conflicts
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_idempotent_retry_returns_same_result_without_extra_effects():
    """Verify same idempotency key and same payload returns original result without duplicate charges."""
    alice = create_ledger_account(DB_URL)
    bob = create_ledger_account(DB_URL)
    simulate_funding(DB_URL, alice.account_id, AmountPaise(5000))

    idem_key = f"idem-key-{uuid4()}"
    amt = AmountPaise(2000)

    # Call 1
    res1 = execute_local_transfer(
        DB_URL,
        idempotency_key=idem_key,
        source_account_id=alice.account_id,
        destination_account_id=bob.account_id,
        amount=amt,
    )

    # Call 2 (retry)
    res2 = execute_local_transfer(
        DB_URL,
        idempotency_key=idem_key,
        source_account_id=alice.account_id,
        destination_account_id=bob.account_id,
        amount=amt,
    )

    assert res1["transfer_id"] == res2["transfer_id"]
    assert res1["journal_id"] == res2["journal_id"]

    # Alice balance must have been debited ONCE (3000 left)
    alice_bal = get_account_balance(DB_URL, alice.account_id)
    bob_bal = get_account_balance(DB_URL, bob.account_id)
    assert alice_bal.posted_balance_minor == 3000
    assert bob_bal.posted_balance_minor == 2000


@pytest.mark.integration
def test_idempotency_conflict_on_changed_payload():
    """Verify reusing same key with a different payload raises IdempotencyConflictError."""
    alice = create_ledger_account(DB_URL)
    bob = create_ledger_account(DB_URL)
    simulate_funding(DB_URL, alice.account_id, AmountPaise(5000))

    idem_key = f"idem-conflict-{uuid4()}"

    # First request: 2000 paise
    execute_local_transfer(
        DB_URL,
        idempotency_key=idem_key,
        source_account_id=alice.account_id,
        destination_account_id=bob.account_id,
        amount=AmountPaise(2000),
    )

    # Reusing same key with 3000 paise must raise conflict
    with pytest.raises(IdempotencyConflictError, match="different payload"):
        execute_local_transfer(
            DB_URL,
            idempotency_key=idem_key,
            source_account_id=alice.account_id,
            destination_account_id=bob.account_id,
            amount=AmountPaise(3000),
        )

    # Balances unaffected by the conflicting call
    alice_bal = get_account_balance(DB_URL, alice.account_id)
    assert alice_bal.posted_balance_minor == 3000


# ---------------------------------------------------------------------------
# 3. Signature Concurrency Invariant: 100 Withdrawals of 80 Against 100
# ---------------------------------------------------------------------------


@pytest.mark.concurrency
@pytest.mark.integration
def test_signature_concurrent_100_withdrawals_of_80_against_100():
    """MANDATORY GATE: 100 concurrent withdrawals of 80 against balance of 100.

    Expected: exactly ONE succeeds; 99 reject with insufficient funds; final balance is 20.
    """
    account = create_ledger_account(DB_URL)
    # Fund account with 100 paise
    simulate_funding(DB_URL, account.account_id, AmountPaise(100))

    initial_bal = get_account_balance(DB_URL, account.account_id)
    assert initial_bal.posted_balance_minor == 100

    def attempt_withdrawal(worker_id: int) -> bool:
        try:
            simulate_cash_out(
                DB_URL,
                account.account_id,
                AmountPaise(80),
                correlation_id=f"concurrent-worker-{worker_id}",
            )
            return True
        except Exception:
            return False

    successes = 0
    failures = 0

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(attempt_withdrawal, i) for i in range(100)]
        for f in as_completed(futures):
            if f.result():
                successes += 1
            else:
                failures += 1

    # Invariant assertions
    assert successes == 1, f"Expected exactly 1 successful withdrawal, got {successes}"
    assert failures == 99, f"Expected exactly 99 rejected withdrawals, got {failures}"

    final_bal = get_account_balance(DB_URL, account.account_id)
    assert final_bal.posted_balance_minor == 20, (
        f"Expected final posted balance 20, got {final_bal.posted_balance_minor}"
    )
    assert final_bal.available_balance_minor == 20
    assert final_bal.account_sequence == 2  # 1 funding + 1 successful cash-out


# ---------------------------------------------------------------------------
# 4. Opposite-Direction Concurrency (Deadlock Prevention)
# ---------------------------------------------------------------------------


@pytest.mark.concurrency
@pytest.mark.integration
def test_opposite_direction_concurrent_transfers_no_deadlocks():
    """Verify simultaneous opposite transfers (Alice->Bob and Bob->Alice) do not deadlock."""
    alice = create_ledger_account(DB_URL)
    bob = create_ledger_account(DB_URL)
    simulate_funding(DB_URL, alice.account_id, AmountPaise(10000))
    simulate_funding(DB_URL, bob.account_id, AmountPaise(10000))

    def xfer(from_id, to_id, worker_id):
        return execute_local_transfer(
            DB_URL,
            idempotency_key=f"opp-xfer-{worker_id}-{uuid4()}",
            source_account_id=from_id,
            destination_account_id=to_id,
            amount=AmountPaise(100),
        )

    tasks = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        # 10 Alice -> Bob
        for i in range(10):
            tasks.append(executor.submit(xfer, alice.account_id, bob.account_id, f"A2B-{i}"))
        # 10 Bob -> Alice
        for i in range(10):
            tasks.append(executor.submit(xfer, bob.account_id, alice.account_id, f"B2A-{i}"))

        results = [t.result() for t in as_completed(tasks)]

    assert len(results) == 20
    alice_bal = get_account_balance(DB_URL, alice.account_id)
    bob_bal = get_account_balance(DB_URL, bob.account_id)

    # 10 transfers each way of 100 paise -> net change is 0
    assert alice_bal.posted_balance_minor == 10000
    assert bob_bal.posted_balance_minor == 10000


# ---------------------------------------------------------------------------
# 5. Full Reversal Semantics
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_full_reversal_happy_path_and_second_reversal_rejection():
    """Verify single full reversal restores balances and second reversal is rejected."""
    alice = create_ledger_account(DB_URL)
    bob = create_ledger_account(DB_URL)
    simulate_funding(DB_URL, alice.account_id, AmountPaise(5000))

    # Transfer 2000 from Alice to Bob
    xfer = execute_local_transfer(
        DB_URL,
        idempotency_key=f"rev-init-{uuid4()}",
        source_account_id=alice.account_id,
        destination_account_id=bob.account_id,
        amount=AmountPaise(2000),
    )
    transfer_id = xfer["transfer_id"]

    # Reversal: Bob -> Alice (2000)
    rev_key = f"rev-key-{uuid4()}"
    rev_res = execute_reversal(
        DB_URL,
        idempotency_key=rev_key,
        original_transfer_id=transfer_id,
        reason="Customer dispute resolved",
    )
    assert rev_res["status"] == "REVERSED"
    assert rev_res["amount_minor"] == 2000

    # Balances restored
    assert get_account_balance(DB_URL, alice.account_id).posted_balance_minor == 5000
    assert get_account_balance(DB_URL, bob.account_id).posted_balance_minor == 0

    # Original transfer marked REVERSED
    details = get_transfer_details(DB_URL, transfer_id)
    assert details["status"] == "REVERSED"
    assert details["is_reversed"] is True

    # Second reversal on same original transfer must be rejected
    with pytest.raises(ReversalConflictError, match="already been reversed"):
        execute_reversal(
            DB_URL,
            idempotency_key=f"rev-second-{uuid4()}",
            original_transfer_id=transfer_id,
        )


@pytest.mark.integration
def test_reversal_rejected_when_recipient_spent_funds():
    """Verify reversal is rejected without forcing an overdraft if recipient lacks funds."""
    alice = create_ledger_account(DB_URL)
    bob = create_ledger_account(DB_URL)
    simulate_funding(DB_URL, alice.account_id, AmountPaise(4000))

    # Transfer 4000 Alice -> Bob
    xfer = execute_local_transfer(
        DB_URL,
        idempotency_key=f"rev-spend-{uuid4()}",
        source_account_id=alice.account_id,
        destination_account_id=bob.account_id,
        amount=AmountPaise(4000),
    )
    transfer_id = xfer["transfer_id"]

    # Bob withdraws 3500, leaving only 500 available
    simulate_cash_out(DB_URL, bob.account_id, AmountPaise(3500))

    # Reversal of 4000 must reject because Bob only has 500 available
    with pytest.raises(ReversalRejectedError, match="insufficient funds for reversal"):
        execute_reversal(
            DB_URL,
            idempotency_key=f"rev-try-{uuid4()}",
            original_transfer_id=transfer_id,
        )

    # Bob balance cannot become negative
    bob_bal = get_account_balance(DB_URL, bob.account_id)
    assert bob_bal.posted_balance_minor == 500
    assert bob_bal.available_balance_minor == 500


# ---------------------------------------------------------------------------
# 6. REST API End-to-End Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_rest_api_transfer_and_reversal_lifecycle():
    """Test full transfer and reversal lifecycle via the FastAPI HTTP endpoints."""
    # 1. Create two accounts
    r1 = client.post(
        "/v1/accounts", json={"currency": "INR"}, headers={"Idempotency-Key": str(uuid4())}
    )
    assert r1.status_code == 201
    acct1 = r1.json()["account_id"]

    r2 = client.post(
        "/v1/accounts", json={"currency": "INR"}, headers={"Idempotency-Key": str(uuid4())}
    )
    assert r2.status_code == 201
    acct2 = r2.json()["account_id"]

    # 2. Fund acct1 (INR 150.00)
    rfund = client.post(
        "/v1/funding",
        json={"account_id": acct1, "amount_minor": 15000},
        headers={**AUTH_HEADERS, "Idempotency-Key": str(uuid4())},
    )
    assert rfund.status_code == 201

    # 3. Transfer 6000 from acct1 to acct2
    idem_key = str(uuid4())
    rxfer = client.post(
        "/v1/transfers",
        json={
            "source_account_id": acct1,
            "destination_account_id": acct2,
            "amount_minor": 6000,
        },
        headers={"Idempotency-Key": idem_key},
    )
    assert rxfer.status_code == 200
    transfer_id = rxfer.json()["transfer_id"]

    # 4. Verify balance
    rb1 = client.get(f"/v1/accounts/{acct1}/balance")
    assert rb1.status_code == 200
    assert rb1.json()["available_balance_minor"] == 9000

    rb2 = client.get(f"/v1/accounts/{acct2}/balance")
    assert rb2.status_code == 200
    assert rb2.json()["available_balance_minor"] == 6000

    # 5. Reverse transfer
    rrev = client.post(
        f"/v1/transfers/{transfer_id}/reversal",
        json={"reason": "Testing API reversal"},
        headers={**AUTH_HEADERS, "Idempotency-Key": str(uuid4())},
    )
    assert rrev.status_code == 200
    assert rrev.json()["status"] == "REVERSED"

    # 6. Verify restored balances
    assert client.get(f"/v1/accounts/{acct1}/balance").json()["available_balance_minor"] == 15000
    assert client.get(f"/v1/accounts/{acct2}/balance").json()["available_balance_minor"] == 0

    # 7. Run reconciliation via admin endpoint
    rrec = client.post("/v1/admin/reconciliation-runs", headers=AUTH_HEADERS)
    assert rrec.status_code == 200
    assert rrec.json()["status"] == "PASS"


@pytest.mark.integration
def test_rest_api_security_and_idempotency_enforcement():
    """Verify unauthorized requests and missing idempotency headers are rejected."""
    # Mutating operation without Idempotency-Key -> 400
    r_no_idem = client.post(
        "/v1/transfers",
        json={
            "source_account_id": str(uuid4()),
            "destination_account_id": str(uuid4()),
            "amount_minor": 1000,
        },
    )
    assert r_no_idem.status_code == 400

    # Protected admin route without Bearer token -> 401
    r_no_auth = client.post("/v1/admin/reconciliation-runs")
    assert r_no_auth.status_code == 401

    # Protected admin route with invalid token -> 403
    r_bad_auth = client.post(
        "/v1/admin/reconciliation-runs",
        headers={"Authorization": "Bearer bad-token-xyz"},
    )
    assert r_bad_auth.status_code == 403
