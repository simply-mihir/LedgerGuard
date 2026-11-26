"""Regression tests for console/API consistency, ledger routing, and session-bound identity."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from starlette.testclient import TestClient

from ledgerguard.api.app import app
from ledgerguard.auth.models import CreateOperatorRequest
from ledgerguard.auth.service import create_operator_account
from ledgerguard.config import settings
from ledgerguard.coordinator.directory_service import provision_account, register_customer
from ledgerguard.domain.money import AmountPaise
from ledgerguard.participant.posting_service import simulate_funding

client = TestClient(app)
TRUSTED_ORIGIN = "http://localhost:3300"
AUTH = {"Authorization": f"Bearer {settings.api_bearer_token}"}


def _login(role: str) -> dict[str, str]:
    uid = uuid4().hex[:8]
    pwd = f"Pass_{uid}!Secure123"
    op = create_operator_account(
        CreateOperatorRequest(
            username=f"{role.lower()}_{uid}",
            email=f"{role.lower()}_{uid}@ledgerguard.internal",
            password=pwd,
            role=role,  # type: ignore[arg-type]
        )
    )
    resp = TestClient(app).post(
        "/v1/auth/login", json={"identifier": op.username, "password": pwd}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["operator"]["role"] == role
    return {
        "username": op.username,
        "cookie": f"ledgerguard_session={resp.cookies['ledgerguard_session']}",
        "csrf": resp.json()["csrf_token"],
    }


def _headers(s: dict[str, str]) -> dict[str, str]:
    return {"Cookie": s["cookie"], "X-CSRF-Token": s["csrf"], "Origin": TRUSTED_ORIGIN}


@pytest.mark.integration
@pytest.mark.parametrize("role", ["VIEWER", "APPROVER"])
def test_rbac_roles_can_authenticate(role: str) -> None:
    """Roles permitted by the database constraint must not break login or session reads."""
    s = _login(role)
    resp = client.get("/v1/auth/session", headers={"Cookie": s["cookie"]})
    assert resp.status_code == 200
    assert resp.json()["operator"]["role"] == role


@pytest.mark.integration
def test_ledger2_account_balance_and_statement_resolve_via_directory() -> None:
    urls = {"ledger-1": settings.ledger1_db_url, "ledger-2": settings.ledger2_db_url}
    suffix = uuid4().hex[:8]
    cust = register_customer(settings.coordinator_db_url, "L2 Owner", f"l2-{suffix}@synthetic.local")
    acct = provision_account(
        settings.coordinator_db_url, urls, UUID(str(cust["customer_id"])), "ledger-2"
    )
    acct_id = UUID(str(acct["account_id"]))
    simulate_funding(settings.ledger2_db_url, acct_id, AmountPaise(12_345))

    bal = client.get(f"/v1/accounts/{acct_id}/balance", headers=AUTH)
    assert bal.status_code == 200, bal.text
    assert bal.json()["posted_balance_minor"] == 12_345

    stmt = client.get(f"/v1/accounts/{acct_id}/statement?limit=10", headers=AUTH)
    assert stmt.status_code == 200, stmt.text
    assert len(stmt.json()["entries"]) >= 1

    assert client.get(f"/v1/accounts/{uuid4()}/balance", headers=AUTH).status_code == 404


@pytest.mark.integration
def test_session_cannot_forge_approval_identity() -> None:
    """A browser session must act as itself: client-supplied identity/role are ignored."""
    s = _login("OPERATOR")
    created = client.post(
        "/v1/operator/approvals",
        headers=_headers(s),
        json={
            "action_type": "MANUAL_RECOVERY_OVERRIDE",
            "payload": {"transfer_id": f"tx-{uuid4().hex[:6]}"},
            "initiator_id": "someone-else",
            "initiator_role": "ADMIN",
        },
    )
    assert created.status_code == 200, created.text
    rid = created.json()["request_id"]
    assert created.json()["initiator_id"] == s["username"]

    # Self-approval is still rejected even if the client claims another identity,
    # a privileged role, and MFA.
    forged = client.post(
        f"/v1/operator/approvals/{rid}/approve",
        headers=_headers(s),
        json={"approver_id": "another-person", "approver_role": "ADMIN", "mfa_verified": True},
    )
    assert forged.status_code == 403, forged.text


@pytest.mark.integration
def test_cookie_mutation_rejects_same_host_different_port_origin() -> None:
    """Origin must match scheme+host+port, not merely hostname/Host header."""
    s = _login("ADMIN")
    bad = {**_headers(s), "Origin": "http://localhost:9999"}
    resp = client.post("/v1/admin/reconciliation-runs", headers=bad)
    assert resp.status_code == 403
    ok = client.post("/v1/admin/reconciliation-runs", headers=_headers(s))
    assert ok.status_code == 200, ok.text
    # Missing CSRF is what the console previously sent: must still be rejected.
    no_csrf = client.post(
        "/v1/admin/reconciliation-runs",
        headers={"Cookie": s["cookie"], "Origin": TRUSTED_ORIGIN},
    )
    assert no_csrf.status_code == 403


@pytest.mark.integration
@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("POST", "/v1/customers", {"name": "X", "email": "x@synthetic.local"}),
        ("POST", "/v1/accounts", {"currency": "INR"}),
        ("GET", f"/v1/accounts/{UUID(int=1)}/balance", None),
        ("GET", f"/v1/accounts/{UUID(int=1)}/statement", None),
        (
            "POST",
            "/v1/transfers",
            {
                "source_account_id": str(UUID(int=1)),
                "destination_account_id": str(UUID(int=2)),
                "amount_minor": 100,
            },
        ),
        ("GET", f"/v1/transfers/{UUID(int=1)}", None),
        ("GET", "/v1/admin/reconciliation-runs/none", None),
    ],
)
def test_financial_routes_require_authentication(
    method: str, path: str, body: dict[str, object] | None
) -> None:
    """Every money-moving or balance-revealing route rejects anonymous callers."""
    anon = TestClient(app)
    headers = {"Idempotency-Key": str(uuid4())}
    resp = anon.request(method, path, json=body, headers=headers)
    assert resp.status_code == 401, (path, resp.text)
    bad = anon.request(
        method, path, json=body, headers={**headers, "Authorization": "Bearer wrong-token"}
    )
    assert bad.status_code == 403, (path, bad.text)
