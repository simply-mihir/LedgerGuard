"""Authentication and authorization utilities for the LedgerGuard API."""

import secrets

from fastapi import Header, HTTPException, Request, status

from ledgerguard.auth.dependencies import (
    COOKIE_SESSION_NAME,
)
from ledgerguard.auth.service import validate_session
from ledgerguard.config import settings


def verify_bearer_token(
    request: Request,
    authorization: str | None = Header(default=None),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> None:
    """Verify that a request provides a valid operator bearer token or active session cookie."""
    # 1. Check session cookie first
    session_cookie = request.cookies.get(COOKIE_SESSION_NAME)
    if session_cookie:
        operator, expected_csrf = validate_session(session_cookie)
        if operator:
            # Enforce CSRF token on mutating actions when using cookie authentication
            if request.method in ("POST", "PUT", "PATCH", "DELETE"):
                if not x_csrf_token or not expected_csrf or not secrets.compare_digest(x_csrf_token, expected_csrf):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Invalid or missing CSRF token.",
                    )
            return

    # 2. Check Authorization header
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Operator authentication required (missing Authorization header or session cookie).",
            headers={"WWW-Authenticate": "Bearer, Cookie"},
        )

    parts = authorization.strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization format; expected 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not secrets.compare_digest(parts[1], settings.api_bearer_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or expired bearer token",
        )


def require_idempotency_key(
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> str:
    """Ensure mutating requests include a non-empty Idempotency-Key header."""
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Header 'Idempotency-Key' is required for mutating operations",
        )
    return idempotency_key.strip()
