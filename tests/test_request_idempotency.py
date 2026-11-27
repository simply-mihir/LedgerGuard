"""Funding, cash-out and account creation honour Idempotency-Key: a retry never writes twice."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import psycopg
import pytest
from starlette.testclient import TestClient

from ledgerguard.api.app import app
from ledgerguard.api.routes import get_ledger_db_url
from ledgerguard.config import settings
from ledgerguard.participant.account_service import create_ledger_account, get_account_balance

client = TestClient(app)
H = {"Authorization": f"Bearer {settings.api_bearer_token}"}
ADMIN = settings.ledger1_admin_db_url


def _acct() -> UUID:
    return create_ledger_account(get_ledger_db_url()).account_id


def _post(path: str, key: str, **body: object):
    return client.post(path, headers={**H, "Idempotency-Key": key}, json=body)


def _balance(a: UUID) -> int:
    return get_account_balance(get_ledger_db_url(), a).posted_balance_minor


def _journals_for(corr: str) -> int:
    with psycopg.connect(ADMIN) as c:
        return int(c.execute("SELECT count(*) FROM journal_headers WHERE correlation_id = %s",
                             (corr,)).fetchone()[0])  # type: ignore[index]


@pytest.mark.integration
def test_funding_retry_with_the_same_key_credits_once_and_replays_the_result() -> None:
    a, key = _acct(), f"fund-{uuid4()}"
    results = [_post("/v1/funding", key, account_id=str(a), amount_minor=1000) for _ in range(3)]
    assert [r.status_code for r in results] == [201, 201, 201]
    assert results[0].json() == results[1].json() == results[2].json()
    assert _balance(a) == 1000
    assert _journals_for(key) == 1


@pytest.mark.integration
def test_reusing_a_key_for_a_different_amount_or_account_is_a_conflict() -> None:
    a, key = _acct(), f"fund-{uuid4()}"
    assert _post("/v1/funding", key, account_id=str(a), amount_minor=1000).status_code == 201
    assert _post("/v1/funding", key, account_id=str(a), amount_minor=2000).status_code == 409
    assert _post("/v1/funding", key, account_id=str(_acct()), amount_minor=1000).status_code == 409
    assert _balance(a) == 1000


@pytest.mark.integration
def test_concurrent_duplicate_funding_requests_credit_exactly_once() -> None:
    a, key = _acct(), f"fund-{uuid4()}"
    with ThreadPoolExecutor(max_workers=8) as pool:
        codes = list(pool.map(lambda _: _post("/v1/funding", key, account_id=str(a), amount_minor=500).status_code,
                              range(8)))
    assert set(codes) == {201}
    assert _balance(a) == 500
    assert _journals_for(key) == 1


@pytest.mark.integration
def test_distinct_keys_post_independently() -> None:
    a = _acct()
    for _ in range(3):
        assert _post("/v1/funding", f"fund-{uuid4()}", account_id=str(a), amount_minor=100).status_code == 201
    assert _balance(a) == 300


@pytest.mark.integration
def test_cash_out_retry_debits_once() -> None:
    a = _acct()
    assert _post("/v1/funding", f"fund-{uuid4()}", account_id=str(a), amount_minor=5000).status_code == 201
    key = f"out-{uuid4()}"
    codes = [_post("/v1/cash-outs", key, account_id=str(a), amount_minor=1000).status_code for _ in range(3)]
    assert codes == [201, 201, 201]
    assert _balance(a) == 4000


@pytest.mark.integration
def test_a_rejected_request_leaves_no_claim_so_the_same_key_can_be_retried() -> None:
    a, key = _acct(), f"out-{uuid4()}"
    assert _post("/v1/cash-outs", key, account_id=str(a), amount_minor=1000).status_code == 422  # no funds
    assert _post("/v1/funding", f"fund-{uuid4()}", account_id=str(a), amount_minor=1000).status_code == 201
    assert _post("/v1/cash-outs", key, account_id=str(a), amount_minor=1000).status_code == 201
    assert _balance(a) == 0


@pytest.mark.integration
def test_account_creation_retry_returns_the_same_account() -> None:
    key = f"acct-{uuid4()}"
    first = _post("/v1/accounts", key, currency="INR", name="idem")
    second = _post("/v1/accounts", key, currency="INR", name="idem")
    assert first.status_code == second.status_code == 201
    assert first.json()["account_id"] == second.json()["account_id"]
    with psycopg.connect(ADMIN) as c:
        assert c.execute("SELECT count(*) FROM ledger_accounts WHERE name = 'idem' AND account_id = %s",
                         (first.json()["account_id"],)).fetchone()[0] == 1  # type: ignore[index]
    assert _post("/v1/accounts", key, currency="INR", name="different").status_code == 409


@pytest.mark.integration
def test_runtime_role_cannot_delete_or_rewrite_claims() -> None:
    url = settings.ledger1_db_url
    with psycopg.connect(url, autocommit=True) as c:
        for sql in ("DELETE FROM request_idempotency", "UPDATE request_idempotency SET request_hash = 'x'",
                    "UPDATE request_idempotency SET idempotency_key = 'x'"):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                c.execute(sql)
