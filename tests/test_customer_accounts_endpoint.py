"""The customer accounts endpoint reads through row-level security: each customer sees only their own."""

from __future__ import annotations

from uuid import uuid4

import pytest
from starlette.testclient import TestClient

from ledgerguard.api.app import app
from ledgerguard.config import settings
from ledgerguard.domain.money import AmountPaise
from ledgerguard.participant.account_service import create_ledger_account
from ledgerguard.participant.customer_view import list_customer_accounts
from ledgerguard.participant.posting_service import simulate_funding

pytestmark = pytest.mark.integration
client = TestClient(app)
H = {"Authorization": f"Bearer {settings.api_bearer_token}"}


def test_each_customer_sees_only_their_own_accounts_and_balances() -> None:
    url = settings.ledger1_db_url
    c1, c2 = uuid4(), uuid4()
    a1 = create_ledger_account(url, customer_id=c1).account_id
    a2 = create_ledger_account(url, customer_id=c2).account_id
    simulate_funding(url, a1, AmountPaise(4_000))
    simulate_funding(url, a2, AmountPaise(9_000))

    r1 = client.get(f"/v1/customers/{c1}/accounts", headers=H)
    assert r1.status_code == 200
    got = {a["account_id"]: a for a in r1.json()["accounts"]}
    assert set(got) == {str(a1)}
    assert got[str(a1)]["posted_balance_minor"] == 4_000
    assert got[str(a1)]["ledger_id"] == "ledger-1"

    r2 = client.get(f"/v1/customers/{c2}/accounts", headers=H)
    assert {a["account_id"] for a in r2.json()["accounts"]} == {str(a2)}


def test_an_unknown_customer_sees_nothing_and_the_endpoint_requires_auth() -> None:
    assert client.get(f"/v1/customers/{uuid4()}/accounts", headers=H).json()["accounts"] == []
    assert client.get(f"/v1/customers/{uuid4()}/accounts").status_code == 401


def test_the_database_scopes_the_query_even_though_it_has_no_customer_predicate() -> None:
    url = settings.ledger1_db_url
    c1, c2 = uuid4(), uuid4()
    create_ledger_account(url, customer_id=c1)
    create_ledger_account(url, customer_id=c2)
    # The helper's SQL contains no WHERE customer_id: only row-level security separates the two.
    import inspect

    from ledgerguard.participant import customer_view
    assert "customer_id =" not in inspect.getsource(customer_view)
    assert len(list_customer_accounts(url, c1)) == 1
