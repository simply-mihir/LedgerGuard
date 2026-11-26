"""Authentication and authorization utilities for the LedgerGuard API."""

from fastapi import Depends, Header, HTTPException, status

from ledgerguard.auth.dependencies import require_authenticated
from ledgerguard.auth.models import OperatorPublicInfo


def verify_bearer_token(_: OperatorPublicInfo = Depends(require_authenticated)) -> None:
    """Route guard: authenticated operator (cookie+CSRF+origin, or service bearer token).

    Thin alias over the single auth path in ``ledgerguard.auth.dependencies``; read-only roles
    are rejected on mutating methods.
    """


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
