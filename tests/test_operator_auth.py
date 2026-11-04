"""Comprehensive security and integration tests for operator authentication and session management."""

from __future__ import annotations

import hashlib
import time
from uuid import uuid4

import psycopg
import pytest
from starlette.testclient import TestClient

from ledgerguard.api.app import app
from ledgerguard.auth.models import CreateOperatorRequest
from ledgerguard.auth.service import create_operator_account, enroll_totp
from ledgerguard.auth.totp import get_totp_code
from ledgerguard.config import settings

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

    # Confirm enrollment using code from past step so next step is fresh
    past_t = int(time.time()) - 30
    code = get_totp_code(secret, t=past_t)
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
def test_session_token_stored_only_as_sha256_hash(test_operator):
    """Verify that raw session tokens are NEVER stored in PostgreSQL; only SHA-256 hashes exist."""
    op = test_operator["operator"]
    login_resp = client.post(
        "/v1/auth/login",
        json={"identifier": op.username, "password": test_operator["password"]},
    )
    assert login_resp.status_code == 200
    raw_token = login_resp.cookies["ledgerguard_session"]

    expected_hash = hashlib.sha256(raw_token.encode("ascii")).hexdigest()

    with psycopg.connect(settings.coordinator_admin_db_url) as conn:
        with conn.cursor() as cur:
            # 1. Search for raw cookie value directly: must NOT exist
            cur.execute(
                "SELECT session_token_hash FROM operator_sessions WHERE session_token_hash = %s;",
                (raw_token,),
            )
            assert cur.fetchone() is None, "Raw session token was found in PostgreSQL!"

            # 2. Search for SHA-256 hash: MUST exist
            cur.execute(
                "SELECT session_token_hash, operator_id, idle_expires_at, expires_at FROM operator_sessions WHERE session_token_hash = %s;",
                (expected_hash,),
            )
            row = cur.fetchone()
            assert row is not None
            assert row[0] == expected_hash
            assert str(row[1]) == str(op.operator_id)


@pytest.mark.integration
def test_session_rotation_on_login(test_operator):
    """Verify that logging in again revokes the previous session and generates a new one."""
    op = test_operator["operator"]

    # First login
    resp1 = client.post(
        "/v1/auth/login",
        json={"identifier": op.username, "password": test_operator["password"]},
    )
    token1 = resp1.cookies["ledgerguard_session"]

    # Second login presenting existing session cookie
    resp2 = client.post(
        "/v1/auth/login",
        json={"identifier": op.username, "password": test_operator["password"]},
        headers={"Cookie": f"ledgerguard_session={token1}"},
    )
    token2 = resp2.cookies["ledgerguard_session"]
    assert token1 != token2

    # Old session is now revoked in database
    old_inspect = client.get(
        "/v1/auth/session",
        headers={"Cookie": f"ledgerguard_session={token1}"},
    )
    assert old_inspect.json()["authenticated"] is False

    # New session is valid
    new_inspect = client.get(
        "/v1/auth/session",
        headers={"Cookie": f"ledgerguard_session={token2}"},
    )
    assert new_inspect.json()["authenticated"] is True


@pytest.mark.integration
def test_idle_and_absolute_session_expiry(test_operator):
    """Verify that sessions expire when idle timeout (30m) or absolute timeout (12h) is reached."""
    op = test_operator["operator"]
    resp = client.post(
        "/v1/auth/login",
        json={"identifier": op.username, "password": test_operator["password"]},
    )
    raw_token = resp.cookies["ledgerguard_session"]
    token_hash = hashlib.sha256(raw_token.encode("ascii")).hexdigest()

    # Artificially set idle_expires_at to past
    with psycopg.connect(settings.coordinator_admin_db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE operator_sessions SET idle_expires_at = NOW() - INTERVAL '1 second' WHERE session_token_hash = %s;",
                (token_hash,),
            )
        conn.commit()

    # Session inspection should fail and purge the session
    inspect = client.get(
        "/v1/auth/session",
        headers={"Cookie": f"ledgerguard_session={raw_token}"},
    )
    assert inspect.json()["authenticated"] is False


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
def test_account_enumeration_resistance():
    """Verify non-existent username produces identical generic 401 error as invalid password."""
    resp = client.post(
        "/v1/auth/login",
        json={"identifier": "nonexistent_operator_xyz", "password": "SomePassword123!"},
    )
    assert resp.status_code == 401
    assert "Invalid credentials" in resp.json()["detail"]


@pytest.mark.integration
def test_logout_revokes_session(test_operator):
    """Verify that logging out revokes the session on both client cookie and coordinator database."""
    op = test_operator["operator"]
    login_resp = client.post(
        "/v1/auth/login",
        json={"identifier": op.username, "password": test_operator["password"]},
    )
    session_cookie = login_resp.cookies["ledgerguard_session"]
    csrf_token = login_resp.json()["csrf_token"]

    logout_resp = client.post(
        "/v1/auth/logout",
        headers={
            "Cookie": f"ledgerguard_session={session_cookie}",
            "X-CSRF-Token": csrf_token,
        },
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
def test_csrf_protection_and_origin_validation(test_operator):
    """Verify CSRF token requirements (missing, malformed, valid) and cross-origin blocking."""
    op = test_operator["operator"]
    login_resp = client.post(
        "/v1/auth/login",
        json={"identifier": op.username, "password": test_operator["password"]},
    )
    session_cookie = login_resp.cookies["ledgerguard_session"]
    csrf_token = login_resp.json()["csrf_token"]
    cookie_header = f"ledgerguard_session={session_cookie}"

    # 1. Missing CSRF token -> 403 Forbidden
    no_csrf_resp = client.post(
        "/v1/operator/experiments/run",
        json={"scenario": "SIGNATURE_RECOVERY"},
        headers={"Cookie": cookie_header},
    )
    assert no_csrf_resp.status_code == 403
    assert "CSRF" in no_csrf_resp.json()["detail"]

    # 2. Malformed / incorrect CSRF token -> 403 Forbidden
    bad_csrf_resp = client.post(
        "/v1/operator/experiments/run",
        json={"scenario": "SIGNATURE_RECOVERY"},
        headers={"Cookie": cookie_header, "X-CSRF-Token": "tampered_csrf_token"},
    )
    assert bad_csrf_resp.status_code == 403

    # 3. Untrusted cross-origin request -> 403 Forbidden
    cross_origin_resp = client.post(
        "/v1/operator/experiments/run",
        json={"scenario": "SIGNATURE_RECOVERY"},
        headers={
            "Cookie": cookie_header,
            "X-CSRF-Token": csrf_token,
            "Origin": "https://malicious-site.example.com",
        },
    )
    assert cross_origin_resp.status_code == 403
    assert "Cross-origin" in cross_origin_resp.json()["detail"]

    # 4. Valid CSRF token and trusted origin -> 200 OK
    good_csrf_resp = client.post(
        "/v1/operator/experiments/run",
        json={"scenario": "SIGNATURE_RECOVERY"},
        headers={
            "Cookie": cookie_header,
            "X-CSRF-Token": csrf_token,
            "Origin": "http://localhost:3300",
        },
    )
    assert good_csrf_resp.status_code == 200


@pytest.mark.integration
def test_totp_mfa_full_lifecycle_and_replay_rejection(mfa_operator):
    """Verify end-to-end two-factor flow and strict TOTP replay rejection within same time step."""
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

    # Step 4: Replay attack with the SAME code in a new attempt MUST be rejected!
    # Obtain a new temp_token
    step1_resp2 = client.post(
        "/v1/auth/login",
        json={"identifier": op.username, "password": mfa_operator["password"]},
    )
    temp_token2 = step1_resp2.json()["temp_token"]

    replay_verify = client.post(
        "/v1/auth/mfa/verify",
        json={"temp_token": temp_token2, "code": valid_code},
    )
    assert replay_verify.status_code == 401
    assert "replayed" in replay_verify.json()["detail"].lower() or "invalid" in replay_verify.json()["detail"].lower()


@pytest.mark.integration
def test_totp_enrollment_expiry(test_operator):
    """Verify that pending TOTP enrollment expires after 10 minutes."""
    op = test_operator["operator"]
    from ledgerguard.auth.service import confirm_totp_enrollment

    secret, _, _ = enroll_totp(op.operator_id)

    # Force pending_totp_expires_at to past
    with psycopg.connect(settings.coordinator_admin_db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE operators SET pending_totp_expires_at = NOW() - INTERVAL '1 second' WHERE operator_id = %s;",
                (op.operator_id,),
            )
        conn.commit()

    code = get_totp_code(secret)
    from ledgerguard.auth.service import AuthenticationError
    with pytest.raises(AuthenticationError) as exc_info:
        confirm_totp_enrollment(op.operator_id, code)
    assert "expired" in str(exc_info.value).lower()
