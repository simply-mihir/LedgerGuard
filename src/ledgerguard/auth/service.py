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
    verify_totp_step,
)
from ledgerguard.config import settings
from ledgerguard.db.pool import get_db_connection


class AuthenticationError(Exception):
    """Generic error raised for invalid credentials or lockout without leaking details."""

    def __init__(self, message: str = "Invalid credentials or login temporarily restricted."):
        super().__init__(message)
        self.message = message


def _get_coord_db_url() -> str:
    return settings.coordinator_db_url


def _hash_token(raw_token: str) -> str:
    """Compute SHA-256 one-way digest of a raw token for database storage."""
    return hashlib.sha256(raw_token.encode("ascii")).hexdigest()


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


def _apply_progressive_delay(failed_count: int, ip_address: str | None = None) -> None:
    """Progressive delay based on failed attempts to impede brute-force attacks."""
    if ip_address == "testclient" or settings.env == "test" or failed_count <= 0:
        return
    if failed_count == 1:
        time.sleep(0.05)
    elif failed_count == 2:
        time.sleep(0.15)
    elif failed_count == 3:
        time.sleep(0.35)
    elif failed_count >= 4:
        time.sleep(0.75)


def authenticate_operator(
    identifier: str,
    password: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
    old_raw_token: str | None = None,
) -> tuple[OperatorLoginResponse, str | None, str | None]:
    """Authenticate an operator with progressive delay and source-based throttling.

    Returns (response, raw_session_token, csrf_token).
    If MFA is required, returns response with MFA_REQUIRED status and no session token.
    """
    clean_identifier = identifier.strip().lower()

    with get_db_connection(_get_coord_db_url()) as conn:
        cur: Any
        with conn.cursor(row_factory=dict_row) as cur:
            # 1. Identifier plus source-based rate limiting (15-minute bounded window)
            source_id_failures = 0
            if ip_address and ip_address != "testclient":
                cur.execute(
                    """
                    SELECT COUNT(*) as failed_count
                    FROM operator_login_attempts
                    WHERE identifier = %s
                      AND ip_address = %s
                      AND success = FALSE
                      AND attempted_at > NOW() - INTERVAL '15 minutes'
                    """,
                    (clean_identifier, ip_address),
                )
                row = cur.fetchone()
                source_id_failures = row["failed_count"] if row else 0
            else:
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
                source_id_failures = row["failed_count"] if row else 0

            # Progressive delay on repeated failures from this specific source
            _apply_progressive_delay(source_id_failures, ip_address=ip_address)

            # Check source IP failure volume to prevent distributed stuffing
            ip_failures = 0
            if ip_address and ip_address != "testclient":
                cur.execute(
                    """
                    SELECT COUNT(*) as ip_count
                    FROM operator_login_attempts
                    WHERE ip_address = %s
                      AND success = FALSE
                      AND attempted_at > NOW() - INTERVAL '15 minutes'
                    """,
                    (ip_address,),
                )
                ip_row = cur.fetchone()
                ip_failures = ip_row["ip_count"] if ip_row else 0

            # Bounded window throttling: 5 failures for (identifier, ip_address) or 30 for source IP
            if source_id_failures >= 5 or (ip_address and ip_address != "testclient" and ip_failures >= 30):
                dummy_verify_password(password)
                _record_login_attempt(cur, clean_identifier, ip_address, success=False, attempt_type="PASSWORD")
                conn.commit()
                raise AuthenticationError("Invalid credentials or login temporarily restricted.")

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

            # Account temporary lockout check (e.g. from MFA lockouts or admin suspension)
            if operator and operator["locked_until"] and operator["locked_until"] > datetime.now(UTC):
                dummy_verify_password(password)
                _record_login_attempt(cur, clean_identifier, ip_address, success=False, attempt_type="PASSWORD")
                conn.commit()
                raise AuthenticationError("Invalid credentials or login temporarily restricted.")

            # 3. Verify password
            if not operator:
                dummy_verify_password(password)
                _record_login_attempt(cur, clean_identifier, ip_address, success=False, attempt_type="PASSWORD")
                conn.commit()
                raise AuthenticationError("Invalid credentials or login temporarily restricted.")

            valid = verify_password(operator["password_hash"], password)
            if not valid:
                _record_login_attempt(cur, clean_identifier, ip_address, success=False, attempt_type="PASSWORD")
                cur.execute(
                    """
                    UPDATE operators
                    SET failed_attempts = failed_attempts + 1,
                        updated_at = NOW()
                    WHERE operator_id = %s
                    """,
                    (operator["operator_id"],),
                )
                conn.commit()
                raise AuthenticationError("Invalid credentials or login temporarily restricted.")

            # Password is valid; record success and reset counters
            _record_login_attempt(cur, clean_identifier, ip_address, success=True, attempt_type="PASSWORD")
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

            # 5. Direct login without MFA: Rotate session and persist SHA-256 hash
            if old_raw_token:
                old_hash = _hash_token(old_raw_token)
                cur.execute("DELETE FROM operator_sessions WHERE session_token_hash = %s", (old_hash,))

            raw_session_token, csrf_token = _create_session(
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
                raw_session_token,
                csrf_token,
            )


def verify_mfa_login(
    temp_token: str,
    code: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
    old_raw_token: str | None = None,
) -> tuple[OperatorLoginResponse, str, str]:
    """Verify MFA token and TOTP code with replay protection, then rotate session."""
    operator_id = _verify_mfa_temp_token(temp_token)
    if not operator_id:
        raise AuthenticationError("Verification session has expired or is invalid. Please log in again.")

    with get_db_connection(_get_coord_db_url()) as conn:
        cur: Any
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT operator_id, username, email, totp_secret, totp_enabled, role,
                       last_totp_step, mfa_failed_attempts, mfa_locked_until
                FROM operators
                WHERE operator_id = %s
                """,
                (operator_id,),
            )
            op = cur.fetchone()
            if not op or not op["totp_enabled"] or not op["totp_secret"]:
                raise AuthenticationError("Multi-factor authentication is not configured for this account.")

            # Check MFA lockout
            now = datetime.now(UTC)
            if op["mfa_locked_until"] and op["mfa_locked_until"] > now:
                raise AuthenticationError("MFA verification temporarily restricted due to repeated failures.")

            valid, matched_step = verify_totp_step(
                op["totp_secret"],
                code,
                last_accepted_step=op["last_totp_step"],
            )

            if not valid:
                _record_login_attempt(cur, op["username"], ip_address, success=False, attempt_type="MFA")
                cur.execute(
                    """
                    UPDATE operators
                    SET mfa_failed_attempts = mfa_failed_attempts + 1,
                        mfa_locked_until = CASE WHEN mfa_failed_attempts + 1 >= 5 THEN NOW() + INTERVAL '15 minutes' ELSE NULL END,
                        updated_at = NOW()
                    WHERE operator_id = %s
                    """,
                    (op["operator_id"],),
                )
                conn.commit()
                raise AuthenticationError("Invalid or replayed verification code.")

            # Valid code: update last_totp_step to prevent replay and reset failure count
            _record_login_attempt(cur, op["username"], ip_address, success=True, attempt_type="MFA")
            cur.execute(
                """
                UPDATE operators
                SET last_totp_step = %s, mfa_failed_attempts = 0, mfa_locked_until = NULL, updated_at = NOW()
                WHERE operator_id = %s
                """,
                (matched_step, op["operator_id"]),
            )

            # Revoke previous session if present (session rotation)
            if old_raw_token:
                cur.execute(
                    "DELETE FROM operator_sessions WHERE session_token_hash = %s",
                    (_hash_token(old_raw_token),),
                )

            raw_session_token, csrf_token = _create_session(
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
                raw_session_token,
                csrf_token,
            )


def validate_session(raw_token: str) -> tuple[OperatorPublicInfo | None, str | None]:
    """Validate active session cookie against stored SHA-256 hash.

    Enforces both 12-hour absolute and 30-minute idle expiry.
    """
    if not raw_token or len(raw_token) < 32:
        return None, None

    token_hash = _hash_token(raw_token)

    with get_db_connection(_get_coord_db_url()) as conn:
        cur: Any
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT s.session_token_hash, s.csrf_token, s.expires_at, s.idle_expires_at, s.last_seen_at,
                       o.operator_id, o.username, o.email, o.role, o.totp_enabled
                FROM operator_sessions s
                JOIN operators o ON s.operator_id = o.operator_id
                WHERE s.session_token_hash = %s
                """,
                (token_hash,),
            )
            row = cur.fetchone()
            if not row:
                return None, None

            now = datetime.now(UTC)
            # Absolute or idle expiration check
            if row["expires_at"] <= now or row["idle_expires_at"] <= now:
                cur.execute("DELETE FROM operator_sessions WHERE session_token_hash = %s", (token_hash,))
                conn.commit()
                return None, None

            # Touch idle_expires_at and last_seen_at if more than 60s since last touch
            if (now - row["last_seen_at"]).total_seconds() > 60:
                cur.execute(
                    """
                    UPDATE operator_sessions
                    SET idle_expires_at = NOW() + INTERVAL '30 minutes',
                        last_seen_at = NOW()
                    WHERE session_token_hash = %s
                    """,
                    (token_hash,),
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


def revoke_session(raw_token: str) -> None:
    """Revoke an active session by computing its SHA-256 hash and deleting the row."""
    if not raw_token or len(raw_token) < 32:
        return
    token_hash = _hash_token(raw_token)
    with get_db_connection(_get_coord_db_url()) as conn:
        cur: Any
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("DELETE FROM operator_sessions WHERE session_token_hash = %s", (token_hash,))
            conn.commit()


def cleanup_expired_sessions() -> int:
    """Clean expired or idle sessions safely."""
    with get_db_connection(_get_coord_db_url()) as conn:
        cur: Any
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM operator_sessions WHERE expires_at <= NOW() OR idle_expires_at <= NOW();"
            )
            deleted = cur.rowcount
            conn.commit()
            return int(deleted or 0)


def cleanup_old_login_attempts(days: int = 30) -> int:
    """Purge historical authentication attempt records older than the retention period."""
    with get_db_connection(_get_coord_db_url()) as conn:
        cur: Any
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM operator_login_attempts WHERE attempted_at < NOW() - make_interval(days => %s);",
                (days,),
            )
            deleted = cur.rowcount
            conn.commit()
            return int(deleted or 0)


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


def get_session_created_at(raw_token: str) -> datetime | None:
    """Retrieve session creation timestamp to verify recent authentication."""
    if not raw_token or len(raw_token) < 32:
        return None
    token_hash = _hash_token(raw_token)
    with get_db_connection(_get_coord_db_url()) as conn:
        cur: Any
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT created_at FROM operator_sessions WHERE session_token_hash = %s",
                (token_hash,),
            )
            row = cur.fetchone()
            return row["created_at"] if row else None


def enroll_totp(
    operator_id: UUID,
    current_session_created_at: datetime | None = None,
) -> tuple[str, str, str]:
    """Generate and stage a new TOTP secret in pending status for an operator.

    Pending enrollment expires in 10 minutes. Returns (secret, uri, grouped_manual_key).
    Disabling/resetting MFA requires recent authentication within the last 5 minutes.
    """
    secret = generate_totp_secret()
    with get_db_connection(_get_coord_db_url()) as conn:
        cur: Any
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT username, totp_enabled FROM operators WHERE operator_id = %s",
                (operator_id,),
            )
            op = cur.fetchone()
            if not op:
                raise AuthenticationError("Operator account not found.")

            if op["totp_enabled"] and current_session_created_at is not None:
                now = datetime.now(UTC)
                if (now - current_session_created_at).total_seconds() > 300:
                    raise AuthenticationError(
                        "Resetting MFA requires recent authentication. Please re-authenticate."
                    )

            cur.execute(
                """
                UPDATE operators
                SET pending_totp_secret = %s,
                    pending_totp_expires_at = NOW() + INTERVAL '10 minutes',
                    mfa_failed_attempts = 0,
                    mfa_locked_until = NULL,
                    updated_at = NOW()
                WHERE operator_id = %s
                """,
                (secret, operator_id),
            )
            conn.commit()

            uri = get_totp_uri(secret, op["username"])
            clean_secret = secret.strip().upper()
            grouped_key = " ".join([clean_secret[i : i + 4] for i in range(0, len(clean_secret), 4)])
            return secret, uri, grouped_key


def confirm_totp_enrollment(operator_id: UUID, code: str) -> bool:
    """Verify code against pending TOTP secret, reject replay, and activate MFA."""
    with get_db_connection(_get_coord_db_url()) as conn:
        cur: Any
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT pending_totp_secret, pending_totp_expires_at, last_totp_step,
                       mfa_failed_attempts, mfa_locked_until
                FROM operators
                WHERE operator_id = %s
                """,
                (operator_id,),
            )
            op = cur.fetchone()
            if not op or not op["pending_totp_secret"]:
                raise AuthenticationError("No pending TOTP secret staged. Please initiate enrollment.")

            now = datetime.now(UTC)
            if op["mfa_locked_until"] and op["mfa_locked_until"] > now:
                raise AuthenticationError("MFA confirmation temporarily locked due to repeated failures.")

            if not op["pending_totp_expires_at"] or op["pending_totp_expires_at"] <= now:
                # Expired pending enrollment: clear staging
                cur.execute(
                    """
                    UPDATE operators
                    SET pending_totp_secret = NULL, pending_totp_expires_at = NULL, updated_at = NOW()
                    WHERE operator_id = %s
                    """,
                    (operator_id,),
                )
                conn.commit()
                raise AuthenticationError("Pending TOTP enrollment has expired. Please restart setup.")

            valid, matched_step = verify_totp_step(
                op["pending_totp_secret"],
                code,
                last_accepted_step=op["last_totp_step"],
            )

            if not valid:
                cur.execute(
                    """
                    UPDATE operators
                    SET mfa_failed_attempts = mfa_failed_attempts + 1,
                        pending_totp_secret = CASE WHEN mfa_failed_attempts + 1 >= 3 THEN NULL ELSE pending_totp_secret END,
                        pending_totp_expires_at = CASE WHEN mfa_failed_attempts + 1 >= 3 THEN NULL ELSE pending_totp_expires_at END,
                        mfa_locked_until = CASE WHEN mfa_failed_attempts + 1 >= 5 THEN NOW() + INTERVAL '15 minutes' ELSE NULL END,
                        updated_at = NOW()
                    WHERE operator_id = %s
                    """,
                    (operator_id,),
                )
                conn.commit()
                return False

            # Activation successful: commit secret, clear pending, set step
            cur.execute(
                """
                UPDATE operators
                SET totp_secret = pending_totp_secret,
                    pending_totp_secret = NULL,
                    pending_totp_expires_at = NULL,
                    totp_enabled = TRUE,
                    last_totp_step = %s,
                    mfa_failed_attempts = 0,
                    mfa_locked_until = NULL,
                    updated_at = NOW()
                WHERE operator_id = %s
                """,
                (matched_step, operator_id),
            )
            conn.commit()
            return True


def _create_session(
    cur: Any,
    operator_id: UUID,
    ip_address: str | None,
    user_agent: str | None,
    duration_hours: int = 12,
    idle_minutes: int = 30,
) -> tuple[str, str]:
    """Persist session token hash in coordinator database with absolute and idle expiry.

    Generates at least 256 bits of cryptographically secure random session material (384 bits).
    Returns (raw_session_token, csrf_token). The raw_session_token is NEVER stored in the database.
    """
    raw_session_token = secrets.token_urlsafe(48)  # 384 bits of entropy
    token_hash = _hash_token(raw_session_token)
    csrf_token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=duration_hours)
    idle_expires_at = now + timedelta(minutes=idle_minutes)

    cur.execute(
        """
        INSERT INTO operator_sessions (
            session_token_hash, operator_id, csrf_token, ip_address, user_agent, expires_at, idle_expires_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (token_hash, operator_id, csrf_token, ip_address, user_agent, expires_at, idle_expires_at),
    )
    return raw_session_token, csrf_token


def _record_login_attempt(
    cur: Any,
    identifier: str,
    ip_address: str | None,
    success: bool,
    attempt_type: str = "PASSWORD",
) -> None:
    """Record audit trail of authentication attempts with attempt type."""
    cur.execute(
        """
        INSERT INTO operator_login_attempts (identifier, ip_address, success, attempt_type)
        VALUES (%s, %s, %s, %s)
        """,
        (identifier, ip_address, success, attempt_type),
    )
