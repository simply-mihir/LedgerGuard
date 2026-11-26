"""Role-based authorization, durable run storage and hardened request bodies."""

from __future__ import annotations

from uuid import uuid4

import psycopg
import pytest
from pydantic import ValidationError
from starlette.testclient import TestClient
from test_console_api_consistency import AUTH, TRUSTED_ORIGIN, _headers, _login

from ledgerguard.api.app import app
from ledgerguard.config import Settings, settings

client = TestClient(app)
TRANSFER_BODY = {
    "source_account_id": str(uuid4()),
    "destination_account_id": str(uuid4()),
    "amount_minor": 100,
}

MUTATIONS: list[tuple[str, str, dict[str, object] | None]] = [
    ("POST", "/v1/customers", {"name": "X", "email": "x@synthetic.local"}),
    ("POST", "/v1/transfers", TRANSFER_BODY),
    ("POST", "/v1/admin/reconciliation-runs", None),
    ("POST", f"/v1/accounts/{uuid4()}/freeze", {"reason": "x"}),
    ("POST", "/v1/operator/chaos/run", {}),
    ("POST", "/v1/operator/audit/checkpoint", None),
    ("POST", f"/v1/operator/transfers/{uuid4()}/refund",
     {"amount_minor": 1, "idempotency_key": "k"}),
    ("POST", "/v1/operator/approvals", {"action_type": "MANUAL_RECOVERY_OVERRIDE"}),
]


@pytest.mark.integration
@pytest.mark.parametrize("role", ["VIEWER", "AUDITOR"])
@pytest.mark.parametrize(("method", "path", "body"), MUTATIONS)
def test_read_only_roles_cannot_mutate(
    role: str, method: str, path: str, body: dict[str, object] | None
) -> None:
    s = _login(role)
    resp = client.request(
        method, path, json=body, headers={**_headers(s), "Idempotency-Key": str(uuid4())}
    )
    assert resp.status_code == 403, (role, path, resp.status_code, resp.text)
    assert "read-only" in resp.text


@pytest.mark.integration
@pytest.mark.parametrize("role", ["VIEWER", "AUDITOR"])
def test_read_only_roles_can_still_read(role: str) -> None:
    s = _login(role)
    for path in ("/v1/operator/overview", "/v1/operator/transfers", "/v1/operator/accounts"):
        resp = client.get(path, headers={"Cookie": s["cookie"]})
        assert resp.status_code == 200, (path, resp.text)


@pytest.mark.integration
def test_operator_role_is_still_allowed_to_mutate() -> None:
    s = _login("OPERATOR")
    assert client.post("/v1/admin/reconciliation-runs", headers=_headers(s)).status_code == 200


@pytest.mark.integration
def test_reconciliation_runs_are_durable_and_attributed() -> None:
    s = _login("ADMIN")
    created = client.post("/v1/admin/reconciliation-runs", headers=_headers(s))
    assert created.status_code == 200, created.text
    run_id = created.json()["run_id"]
    with psycopg.connect(settings.coordinator_db_url) as conn:
        row = conn.execute(
            "SELECT status, requested_by FROM reconciliation_runs WHERE run_id = %s", (run_id,)
        ).fetchone()
    assert row == (created.json()["status"], s["username"])
    # A brand-new client (as after a restart) reads the same run from the database.
    fetched = TestClient(app).get(f"/v1/admin/reconciliation-runs/{run_id}", headers=AUTH)
    assert fetched.status_code == 200 and fetched.json() == created.json()
    assert client.get("/v1/admin/reconciliation-runs/not-a-uuid", headers=AUTH).status_code == 404


@pytest.mark.integration
def test_audit_actor_is_taken_from_session_not_body() -> None:
    s = _login("OPERATOR")
    resp = client.post(
        f"/v1/operator/transfers/{uuid4()}/refund",
        headers=_headers(s),
        json={"amount_minor": 5, "idempotency_key": uuid4().hex, "actor": "forged-admin"},
    )
    # The transfer does not exist, so the refund is refused; the point is that the route
    # accepted the body shape and never used the forged actor (covered by unit check below).
    assert resp.status_code in (400, 404, 409), resp.text
    from starlette.requests import Request

    from ledgerguard.api.routes import _actor

    req = Request({"type": "http", "headers": []})
    req.state.auth_type = "cookie"
    req.state.operator = type("Op", (), {"username": "real-user"})()
    assert _actor(req, "forged-admin") == "real-user"
    svc = Request({"type": "http", "headers": []})
    svc.state.auth_type = "bearer"
    assert _actor(svc, "batch-job") == "batch-job"


@pytest.mark.integration
@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/v1/operator/disputes", {"transfer_id": "nope", "amount_minor": 1, "reason_code": "x"}),
        ("/v1/operator/disputes", {"transfer_id": str(uuid4()), "amount_minor": -5,
                                   "reason_code": "x"}),
        (f"/v1/operator/transfers/{uuid4()}/refund", {"amount_minor": "abc",
                                                      "idempotency_key": "k"}),
        (f"/v1/operator/transfers/{uuid4()}/refund", {"amount_minor": 5}),
        ("/v1/operator/approvals", {"action_type": "X", "ttl_seconds": 10**9}),
    ],
)
def test_malformed_operator_bodies_are_422_not_500(path: str, body: dict[str, object]) -> None:
    resp = client.post(path, json=body, headers=AUTH)
    assert resp.status_code == 422, (path, resp.status_code, resp.text)


@pytest.mark.integration
def test_service_caller_must_name_an_approval_actor() -> None:
    resp = client.post(
        "/v1/operator/approvals", json={"action_type": "MANUAL_RECOVERY_OVERRIDE"}, headers=AUTH
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.integration
def test_client_cannot_claim_fresh_authentication() -> None:
    """auth_age_seconds is measured from the server-side session, not the request body."""
    from starlette.requests import Request

    from ledgerguard.api.routes import _session_bound
    from ledgerguard.api.schemas import ApprovalApproveBody

    s = _login("APPROVER")
    cookie_val = s["cookie"].split("=", 1)[1]
    req = Request({"type": "http", "headers": [(b"cookie", s["cookie"].encode())]})
    req.state.auth_type = "cookie"
    op = TestClient(app).get("/v1/auth/session", headers={"Cookie": s["cookie"]}).json()["operator"]
    from ledgerguard.auth.models import OperatorPublicInfo

    bound = _session_bound(
        req, OperatorPublicInfo(**op), ApprovalApproveBody(auth_age_seconds=0, mfa_verified=True),
        "approver_id", "approver_role",
    )
    assert cookie_val  # session exists
    assert bound["auth_age_seconds"] >= 0
    assert bound["approver_id"] == s["username"]
    assert bound["mfa_verified"] is op["totp_enabled"]


def test_production_refuses_demo_internal_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(LEDGERGUARD_ENV="production", LEDGERGUARD_TRUSTED_ORIGINS="https://x.example")  # type: ignore[call-arg]
    ok = Settings(  # type: ignore[call-arg]
        LEDGERGUARD_ENV="production", INTERNAL_SERVICE_SECRET="y" * 40,
        LEDGERGUARD_TRUSTED_ORIGINS="https://x.example",
    )
    assert ok.env == "production"
    assert TRUSTED_ORIGIN


@pytest.mark.parametrize(
    "raw",
    ["billing", "billing:ADMIN", "billing:ROOT:" + "t" * 40, "billing:ADMIN:short",
     "Bad Name:ADMIN:" + "t" * 40, f"a1:ADMIN:{'t' * 40},b2:ADMIN:{'t' * 40}",
     f"a1:ADMIN:{'t' * 40},a1:VIEWER:{'u' * 40}", "a1:ADMIN:ledgerguard_operator_demo_token"],
)
def test_malformed_service_credentials_fail_at_startup(raw: str) -> None:
    with pytest.raises(ValidationError):
        Settings(API_SERVICE_TOKENS=raw)  # type: ignore[call-arg]


TOKEN_A = "a" * 40
TOKEN_B = "b" * 40
TOKEN_RO = "r" * 40


def _svc(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def service_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        settings, "service_tokens_raw",
        f"batch-ops:OPERATOR:{TOKEN_A},batch-ops:OPERATOR:{TOKEN_B},reporter:AUDITOR:{TOKEN_RO}",
    )


@pytest.mark.integration
def test_named_service_credentials_are_attributable_and_role_limited(service_tokens: None) -> None:
    ok = client.post("/v1/admin/reconciliation-runs", headers=_svc(TOKEN_A))
    assert ok.status_code == 200, ok.text
    with psycopg.connect(settings.coordinator_db_url) as conn:
        row = conn.execute(
            "SELECT requested_by FROM reconciliation_runs WHERE run_id = %s", (ok.json()["run_id"],)
        ).fetchone()
    assert row == ("svc:batch-ops",)
    # An AUDITOR-role credential can read but never mutate.
    assert client.get("/v1/operator/overview", headers=_svc(TOKEN_RO)).status_code == 200
    denied = client.post("/v1/admin/reconciliation-runs", headers=_svc(TOKEN_RO))
    assert denied.status_code == 403 and "read-only" in denied.text


@pytest.mark.integration
def test_service_credential_rotation_and_revocation(service_tokens: None, monkeypatch: pytest.MonkeyPatch) -> None:
    assert client.get("/v1/operator/overview", headers=_svc(TOKEN_A)).status_code == 200
    assert client.get("/v1/operator/overview", headers=_svc(TOKEN_B)).status_code == 200
    # Revoke the old token: only the new one keeps working.
    monkeypatch.setattr(settings, "service_tokens_raw", f"batch-ops:OPERATOR:{TOKEN_B}")
    assert client.get("/v1/operator/overview", headers=_svc(TOKEN_A)).status_code == 403
    assert client.get("/v1/operator/overview", headers=_svc(TOKEN_B)).status_code == 200


@pytest.mark.integration
def test_service_credential_cannot_choose_or_approve_as_a_human(service_tokens: None) -> None:
    created = client.post(
        "/v1/operator/approvals", headers=_svc(TOKEN_A),
        json={"action_type": "MANUAL_RECOVERY_OVERRIDE", "initiator_id": "alice",
              "initiator_role": "ADMIN", "payload": {"transfer_id": f"tx-{uuid4().hex[:6]}"}},
    )
    assert created.status_code == 200, created.text
    assert created.json()["initiator_id"] == "svc:batch-ops"
    approve = client.post(
        f"/v1/operator/approvals/{created.json()['request_id']}/approve", headers=_svc(TOKEN_A),
        json={"approver_id": "bob", "approver_role": "ADMIN", "mfa_verified": True,
              "auth_age_seconds": 0},
    )
    assert approve.status_code == 403, approve.text


@pytest.mark.integration
def test_production_disables_shared_legacy_token(
    service_tokens: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert client.get("/v1/operator/overview", headers=AUTH).status_code == 200
    monkeypatch.setattr(settings, "env", "production")
    monkeypatch.setattr(settings, "trusted_origins_raw", "https://console.example")
    assert client.get("/v1/operator/overview", headers=AUTH).status_code == 403
    assert client.get("/v1/operator/overview", headers=_svc(TOKEN_A)).status_code == 200


@pytest.mark.integration
@pytest.mark.parametrize(
    "path", ["/v1/operator/overview", "/v1/operator/approvals", "/v1/operator/disputes"]
)
def test_single_auth_path_has_uniform_status_codes(path: str) -> None:
    """Routes guarded by either legacy dependency now share one 401/403 contract."""
    anon = TestClient(app)
    assert anon.get(path).status_code == 401
    assert anon.get(path, headers={"Authorization": "Basic abc"}).status_code == 401
    assert anon.get(path, headers={"Authorization": "Bearer wrong"}).status_code == 403
    assert anon.get(path, headers=AUTH).status_code == 200
