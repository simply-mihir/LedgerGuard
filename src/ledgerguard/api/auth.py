"""Authentication and authorization utilities for the LedgerGuard API."""

from fastapi import Header, HTTPException, status

from ledgerguard.config import settings


def verify_bearer_token(authorization: str | None = Header(default=None)) -> None:
    """Verify that a request provides a valid operator bearer token."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    parts = authorization.strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization format; expected 'Bearer <token>'",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if parts[1] != settings.api_bearer_token:
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
