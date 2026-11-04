"""Comprehensive security and integration tests for operator authentication and session management."""

from __future__ import annotations

from uuid import uuid4

import pytest
from starlette.testclient import TestClient

from ledgerguard.api.app import app
from ledgerguard.auth.models import CreateOperatorRequest
from ledgerguard.auth.service import create_operator_account, enroll_totp
from ledgerguard.auth.totp import get_totp_code

client = TestClient(app)


@pytest.fixture
def test_operator():
    """Create an isolated test operator account without TOTP."""
    uid = uuid4().hex[:8]
    username = f"op_test_{uid}"
    email = f"{username}@ledgerguard.internal"
    pwd = f"Pass_{uid}!Secure123"
    req = CreateOperatorRequest(
        username=username,
        email=email,
        password=pwd,
        role="OPERATOR",
        enable_totp=False,
    )
    op = create_operator_account(req)
    return {"operator": op, "password": pwd}


@pytest.fixture
def mfa_operator():
    """Create an isolated test operator account with TOTP enabled."""
    uid = uuid4().hex[:8]
    username = f"mfa_test_{uid}"
    email = f"{username}@ledgerguard.internal"
    pwd = f"Pass_{uid}!Secure123"
    req = CreateOperatorRequest(
        username=username,
        email=email,
        password=pwd,
        role="ADMIN",
        enable_totp=True,
    )
    op = create_operator_account(req)
    secret, _, _ = enroll_totp(op.operator_id)
    from ledgerguard.auth.service import confirm_totp_enrollment

    code = get_totp_code(secret)
    confirm_totp_enrollment(op.operator_id, code)
    return {"operator": op, "password": pwd, "secret": secret}


@pytest.mark.integration
def test_valid_login_sets_session_cookie(test_operator):
    """Verify that submitting valid credentials sets an HttpOnly session cookie and returns operator metadata."""
    op = test_operator["operator"]
    resp = client.post(
        "/v1/auth/login",
        json={"identifier": op.username, "password": test_operator["password"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert data["csrf_token"] is not None
    assert data["operator"]["username"] == op.username
    assert data["operator"]["role"] == "OPERATOR"

    # Verify cookie presence
    assert "ledgerguard_session" in resp.cookies
    session_cookie = resp.cookies["ledgerguard_session"]
    assert len(session_cookie) >= 32

    # Verify session inspection returns authenticated state
    inspect_resp = client.get(
        "/v1/auth/session",
        headers={"Cookie": f"ledgerguard_session={session_cookie}"},
    )
    assert inspect_resp.status_code == 200
    inspect_data = inspect_resp.json()
    assert inspect_data["authenticated"] is True
    assert inspect_data["operator"]["username"] == op.username
    assert inspect_data["csrf_token"] == data["csrf_token"]


@pytest.mark.integration
def test_invalid_credentials_returns_generic_error(test_operator):
    """Verify that invalid password produces a generic 401 error to prevent enumeration."""
    op = test_operator["operator"]
    resp = client.post(
        "/v1/auth/login",
        json={"identifier": op.username, "password": "WrongPassword123!"},
    )
    assert resp.status_code == 401
    assert "Invalid credentials" in resp.json()["detail"]


@pytest.mark.integration
def test_nonexistent_user_returns_generic_error():
    """Verify non-existent username produces identical generic 401 error."""
    resp = client.post(
        "/v1/auth/login",
        json={"identifier": "nonexistent_operator_xyz", "password": "SomePassword123!"},
    )
    assert resp.status_code == 401
    assert "Invalid credentials" in resp.json()["detail"]


@pytest.mark.integration
def test_rate_limiting_and_lockout_after_failures(test_operator):
    """Verify that 5 repeated failed attempts locks the account."""
    op = test_operator["operator"]

    for _ in range(5):
        resp = client.post(
            "/v1/auth/login",
            json={"identifier": op.username, "password": "BadPassword1!"},
        )
        assert resp.status_code == 401

    # Sixth attempt with valid password should still be locked out
    locked_resp = client.post(
        "/v1/auth/login",
        json={"identifier": op.username, "password": test_operator["password"]},
    )
    assert locked_resp.status_code == 401
    assert "Invalid credentials or account temporarily locked" in locked_resp.json()["detail"]


@pytest.mark.integration
def test_logout_revokes_session(test_operator):
    """Verify that logging out revokes the session on both client cookie and coordinator database."""
    op = test_operator["operator"]
    login_resp = client.post(
        "/v1/auth/login",
        json={"identifier": op.username, "password": test_operator["password"]},
    )
    session_cookie = login_resp.cookies["ledgerguard_session"]

    logout_resp = client.post(
        "/v1/auth/logout",
        headers={"Cookie": f"ledgerguard_session={session_cookie}"},
    )
    assert logout_resp.status_code == 200

    # Session inspection should now return authenticated: False
    inspect_resp = client.get(
        "/v1/auth/session",
        headers={"Cookie": f"ledgerguard_session={session_cookie}"},
    )
    assert inspect_resp.status_code == 200
    assert inspect_resp.json()["authenticated"] is False


@pytest.mark.integration
def test_csrf_protection_on_state_changing_requests(test_operator):
    """Verify that cookie-authenticated state-changing requests require valid X-CSRF-Token."""
    op = test_operator["operator"]
    login_resp = client.post(
        "/v1/auth/login",
        json={"identifier": op.username, "password": test_operator["password"]},
    )
    session_cookie = login_resp.cookies["ledgerguard_session"]
    csrf_token = login_resp.json()["csrf_token"]
    cookie_header = f"ledgerguard_session={session_cookie}"

    # Mutation without CSRF token should be rejected with 403 Forbidden
    no_csrf_resp = client.post(
        "/v1/operator/experiments/run",
        json={"scenario": "SIGNATURE_RECOVERY"},
        headers={"Cookie": cookie_header},
    )
    assert no_csrf_resp.status_code == 403
    assert "CSRF" in no_csrf_resp.json()["detail"]

    # Mutation with invalid CSRF token should also be rejected
    bad_csrf_resp = client.post(
        "/v1/operator/experiments/run",
        json={"scenario": "SIGNATURE_RECOVERY"},
        headers={"Cookie": cookie_header, "X-CSRF-Token": "invalid_forged_csrf_token"},
    )
    assert bad_csrf_resp.status_code == 403

    # Mutation with correct CSRF token should succeed
    good_csrf_resp = client.post(
        "/v1/operator/experiments/run",
        json={"scenario": "SIGNATURE_RECOVERY"},
        headers={"Cookie": cookie_header, "X-CSRF-Token": csrf_token},
    )
    assert good_csrf_resp.status_code == 200


@pytest.mark.integration
def test_totp_mfa_full_lifecycle(mfa_operator):
    """Verify end-to-end two-factor authentication flow with RFC 6238 TOTP."""
    op = mfa_operator["operator"]
    secret = mfa_operator["secret"]

    # Step 1: Initial login returns MFA_REQUIRED and short-lived temp_token
    step1_resp = client.post(
        "/v1/auth/login",
        json={"identifier": op.username, "password": mfa_operator["password"]},
    )
    assert step1_resp.status_code == 200
    step1_data = step1_resp.json()
    assert step1_data["status"] == "MFA_REQUIRED"
    assert "ledgerguard_session" not in step1_resp.cookies
    temp_token = step1_data["temp_token"]
    assert temp_token is not None

    # Step 2: Invalid TOTP code is rejected
    bad_verify = client.post(
        "/v1/auth/mfa/verify",
        json={"temp_token": temp_token, "code": "000000"},
    )
    assert bad_verify.status_code == 401

    # Step 3: Valid 6-digit TOTP code succeeds and sets session
    valid_code = get_totp_code(secret)
    good_verify = client.post(
        "/v1/auth/mfa/verify",
        json={"temp_token": temp_token, "code": valid_code},
    )
    assert good_verify.status_code == 200
    good_data = good_verify.json()
    assert good_data["status"] == "SUCCESS"
    assert "ledgerguard_session" in good_verify.cookies
    assert good_data["operator"]["username"] == op.username
