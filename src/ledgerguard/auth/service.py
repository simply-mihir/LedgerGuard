"""Operator authentication service, session management, and rate-limiting."""

import base64
import hashlib
import hmac
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from ledgerguard.auth.models import (
    CreateOperatorRequest,
    OperatorLoginResponse,
    OperatorPublicInfo,
)
from ledgerguard.auth.password import (
    dummy_verify_password,
    hash_password,
    verify_password,
)
from ledgerguard.auth.totp import (
    generate_totp_secret,
    get_totp_uri,
    verify_totp_code,
)
from ledgerguard.config import settings
from ledgerguard.db.pool import get_db_connection


class AuthenticationError(Exception):
    """Generic error raised for invalid credentials or lockout without leaking details."""

    def __init__(self, message: str = "Invalid credentials or account temporarily locked."):
        super().__init__(message)
        self.message = message


def _get_coord_db_url() -> str:
    return settings.coordinator_db_url


def _generate_mfa_temp_token(operator_id: UUID, ttl_seconds: int = 300) -> str:
    """Generate a tamper-evident short-lived token for MFA completion."""
    expires_at = int(time.time()) + ttl_seconds
    payload = f"{operator_id}:{expires_at}"
    signature = hmac.new(
        settings.internal_service_secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    raw = f"{payload}:{signature}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def _verify_mfa_temp_token(token: str) -> UUID | None:
    """Verify and unpack a short-lived MFA temporary token."""
    try:
        decoded = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
        parts = decoded.split(":")
        if len(parts) != 3:
            return None
        op_id_str, expires_at_str, signature = parts
        payload = f"{op_id_str}:{expires_at_str}"
        expected_sig = hmac.new(
            settings.internal_service_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not secrets.compare_digest(expected_sig, signature):
            return None
        if int(time.time()) > int(expires_at_str):
            return None
        return UUID(op_id_str)
    except Exception:
        return None


def authenticate_operator(
    identifier: str,
    password: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[OperatorLoginResponse, str | None, str | None]:
    """Authenticate an operator. Returns (response, session_id, csrf_token).

    If MFA is required, returns response with MFA_REQUIRED status and no session_id.
    """
    clean_identifier = identifier.strip().lower()

    with get_db_connection(_get_coord_db_url()) as conn:
        cur: Any
        with conn.cursor(row_factory=dict_row) as cur:
            # 1. Check account lockout or recent failed attempts
            cur.execute(
                """
                SELECT COUNT(*) as failed_count
                FROM operator_login_attempts
                WHERE identifier = %s
                  AND success = FALSE
                  AND attempted_at > NOW() - INTERVAL '15 minutes'
                """,
                (clean_identifier,),
            )
            row = cur.fetchone()
            recent_failures = row["failed_count"] if row else 0

            # 2. Lookup operator by username or email
            cur.execute(
                """
                SELECT operator_id, username, email, password_hash,
                       totp_secret, totp_enabled, role, failed_attempts, locked_until
                FROM operators
                WHERE LOWER(username) = %s OR LOWER(email) = %s
                """,
                (clean_identifier, clean_identifier),
            )
            operator = cur.fetchone()

            # If locked or too many failed attempts, block immediately
            if operator and operator["locked_until"] and operator["locked_until"] > datetime.now(UTC):
                dummy_verify_password(password)
                _record_login_attempt(cur, clean_identifier, ip_address, success=False)
                conn.commit()
                raise AuthenticationError()

            if recent_failures >= 5:
                dummy_verify_password(password)
                if operator:
                    cur.execute(
                        "UPDATE operators SET locked_until = NOW() + INTERVAL '15 minutes' WHERE operator_id = %s",
                        (operator["operator_id"],),
                    )
                _record_login_attempt(cur, clean_identifier, ip_address, success=False)
                conn.commit()
                raise AuthenticationError()

            # 3. Verify password
            if not operator:
                dummy_verify_password(password)
                _record_login_attempt(cur, clean_identifier, ip_address, success=False)
                conn.commit()
                raise AuthenticationError()

            valid = verify_password(operator["password_hash"], password)
            if not valid:
                _record_login_attempt(cur, clean_identifier, ip_address, success=False)
                cur.execute(
                    """
                    UPDATE operators
                    SET failed_attempts = failed_attempts + 1,
                        locked_until = CASE WHEN failed_attempts + 1 >= 5 THEN NOW() + INTERVAL '15 minutes' ELSE NULL END,
                        updated_at = NOW()
                    WHERE operator_id = %s
                    """,
                    (operator["operator_id"],),
                )
                conn.commit()
                raise AuthenticationError()

            # Password is valid; reset failure counters and record success
            _record_login_attempt(cur, clean_identifier, ip_address, success=True)
            cur.execute(
                """
                UPDATE operators
                SET failed_attempts = 0, locked_until = NULL, updated_at = NOW()
                WHERE operator_id = %s
                """,
                (operator["operator_id"],),
            )

            public_info = OperatorPublicInfo(
                operator_id=operator["operator_id"],
                username=operator["username"],
                email=operator["email"],
                role=operator["role"],
                totp_enabled=operator["totp_enabled"],
            )

            # 4. Handle MFA if enabled
            if operator["totp_enabled"]:
                temp_token = _generate_mfa_temp_token(operator["operator_id"])
                conn.commit()
                return (
                    OperatorLoginResponse(
                        status="MFA_REQUIRED",
                        temp_token=temp_token,
                        message="Second-factor verification required. Enter the 6-digit code from your authenticator app.",
                    ),
                    None,
                    None,
                )

            # 5. Direct login without MFA: Create server session
            session_id, csrf_token = _create_session(
                cur,
                operator_id=operator["operator_id"],
                ip_address=ip_address,
                user_agent=user_agent,
            )
            conn.commit()

            return (
                OperatorLoginResponse(
                    status="SUCCESS",
                    csrf_token=csrf_token,
                    operator=public_info,
                    message="Operator authentication successful.",
                ),
                session_id,
                csrf_token,
            )


def verify_mfa_login(
    temp_token: str,
    code: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> tuple[OperatorLoginResponse, str, str]:
    """Verify MFA token and TOTP code, then create session."""
    operator_id = _verify_mfa_temp_token(temp_token)
    if not operator_id:
        raise AuthenticationError("Verification session has expired or is invalid. Please log in again.")

    with get_db_connection(_get_coord_db_url()) as conn:
        cur: Any
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT operator_id, username, email, totp_secret, totp_enabled, role
                FROM operators
                WHERE operator_id = %s
                """,
                (operator_id,),
            )
            op = cur.fetchone()
            if not op or not op["totp_enabled"] or not op["totp_secret"]:
                raise AuthenticationError("Multi-factor authentication is not configured for this account.")

            valid = verify_totp_code(op["totp_secret"], code)
            if not valid:
                _record_login_attempt(cur, op["username"], ip_address, success=False)
                conn.commit()
                raise AuthenticationError("Invalid 6-digit verification code.")

            _record_login_attempt(cur, op["username"], ip_address, success=True)
            session_id, csrf_token = _create_session(
                cur,
                operator_id=op["operator_id"],
                ip_address=ip_address,
                user_agent=user_agent,
            )
            conn.commit()

            public_info = OperatorPublicInfo(
                operator_id=op["operator_id"],
                username=op["username"],
                email=op["email"],
                role=op["role"],
                totp_enabled=op["totp_enabled"],
            )

            return (
                OperatorLoginResponse(
                    status="SUCCESS",
                    csrf_token=csrf_token,
                    operator=public_info,
                    message="Multi-factor authentication verified.",
                ),
                session_id,
                csrf_token,
            )


def validate_session(session_id: str) -> tuple[OperatorPublicInfo | None, str | None]:
    """Validate active session cookie and return operator details and csrf_token."""
    if not session_id or len(session_id) < 32:
        return None, None

    with get_db_connection(_get_coord_db_url()) as conn:
        cur: Any
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT s.session_id, s.csrf_token, s.expires_at, s.last_seen_at,
                       o.operator_id, o.username, o.email, o.role, o.totp_enabled
                FROM operator_sessions s
                JOIN operators o ON s.operator_id = o.operator_id
                WHERE s.session_id = %s
                """,
                (session_id,),
            )
            row = cur.fetchone()
            if not row:
                return None, None

            now = datetime.now(UTC)
            if row["expires_at"] <= now:
                # Expired: purge session
                cur.execute("DELETE FROM operator_sessions WHERE session_id = %s", (session_id,))
                conn.commit()
                return None, None

            # Touch last_seen_at if it was more than 1 minute ago
            if (now - row["last_seen_at"]).total_seconds() > 60:
                cur.execute(
                    "UPDATE operator_sessions SET last_seen_at = NOW() WHERE session_id = %s",
                    (session_id,),
                )
                conn.commit()

            public_info = OperatorPublicInfo(
                operator_id=row["operator_id"],
                username=row["username"],
                email=row["email"],
                role=row["role"],
                totp_enabled=row["totp_enabled"],
            )
            return public_info, row["csrf_token"]


def revoke_session(session_id: str) -> None:
    """Revoke an active session upon logout."""
    if not session_id:
        return
    with get_db_connection(_get_coord_db_url()) as conn:
        cur: Any
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("DELETE FROM operator_sessions WHERE session_id = %s", (session_id,))
            conn.commit()


def create_operator_account(req: CreateOperatorRequest) -> OperatorPublicInfo:
    """Provision a new operator with Argon2id password hash."""
    hashed_pwd = hash_password(req.password)
    totp_secret = generate_totp_secret() if req.enable_totp else None

    with get_db_connection(_get_coord_db_url()) as conn:
        cur: Any
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO operators (username, email, password_hash, totp_secret, totp_enabled, role)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING operator_id, username, email, role, totp_enabled
                """,
                (
                    req.username.strip(),
                    req.email.strip().lower(),
                    hashed_pwd,
                    totp_secret,
                    req.enable_totp,
                    req.role,
                ),
            )
            row = cur.fetchone()
            if not row:
                raise RuntimeError("Failed to insert operator row.")
            conn.commit()
            return OperatorPublicInfo(
                operator_id=row["operator_id"],
                username=row["username"],
                email=row["email"],
                role=row["role"],
                totp_enabled=row["totp_enabled"],
            )


def enroll_totp(operator_id: UUID) -> tuple[str, str, str]:
    """Generate and stage a new TOTP secret for an existing operator.

    Returns (secret, provisioning_uri, manual_entry_key).
    """
    secret = generate_totp_secret()
    with get_db_connection(_get_coord_db_url()) as conn:
        cur: Any
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT username FROM operators WHERE operator_id = %s",
                (operator_id,),
            )
            op = cur.fetchone()
            if not op:
                raise AuthenticationError("Operator account not found.")

            cur.execute(
                "UPDATE operators SET totp_secret = %s, totp_enabled = FALSE WHERE operator_id = %s",
                (secret, operator_id),
            )
            conn.commit()

            uri = get_totp_uri(secret, op["username"])
            # Format manual entry key in groups of 4 for human readability
            clean_secret = secret.strip().upper()
            grouped_key = " ".join([clean_secret[i : i + 4] for i in range(0, len(clean_secret), 4)])
            return secret, uri, grouped_key


def confirm_totp_enrollment(operator_id: UUID, code: str) -> bool:
    """Verify code against newly staged TOTP secret and activate MFA."""
    with get_db_connection(_get_coord_db_url()) as conn:
        cur: Any
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT totp_secret FROM operators WHERE operator_id = %s",
                (operator_id,),
            )
            op = cur.fetchone()
            if not op or not op["totp_secret"]:
                raise AuthenticationError("No pending TOTP secret staged.")

            if not verify_totp_code(op["totp_secret"], code):
                return False

            cur.execute(
                "UPDATE operators SET totp_enabled = TRUE, updated_at = NOW() WHERE operator_id = %s",
                (operator_id,),
            )
            conn.commit()
            return True


def _create_session(
    cur: Any,
    operator_id: UUID,
    ip_address: str | None,
    user_agent: str | None,
    duration_hours: int = 12,
) -> tuple[str, str]:
    """Helper to persist a new operator session in the coordinator database."""
    session_id = secrets.token_urlsafe(64)
    csrf_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(hours=duration_hours)

    cur.execute(
        """
        INSERT INTO operator_sessions (session_id, operator_id, csrf_token, ip_address, user_agent, expires_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (session_id, operator_id, csrf_token, ip_address, user_agent, expires_at),
    )
    return session_id, csrf_token


def _record_login_attempt(
    cur: Any,
    identifier: str,
    ip_address: str | None,
    success: bool,
) -> None:
    """Record an audit trail of authentication attempts for brute-force protection."""
    cur.execute(
        """
        INSERT INTO operator_login_attempts (identifier, ip_address, success)
        VALUES (%s, %s, %s)
        """,
        (identifier, ip_address, success),
    )
