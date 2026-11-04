"""FastAPI dependencies for operator session authentication and CSRF protection."""

import secrets
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status

from ledgerguard.auth.models import OperatorPublicInfo
from ledgerguard.auth.service import validate_session
from ledgerguard.config import settings

# Synthetic operator identity when authenticated via internal API bearer token
SYSTEM_OPERATOR = OperatorPublicInfo(
    operator_id=UUID("00000000-0000-0000-0000-000000000001"),
    username="system_operator",
    email="system@ledgerguard.internal",
    role="ADMIN",
    totp_enabled=False,
)

COOKIE_SESSION_NAME = "ledgerguard_session"


def get_current_operator(
    request: Request,
    authorization: str | None = Header(default=None),
) -> OperatorPublicInfo:
    """Authenticate incoming operator request via HttpOnly session cookie or Bearer token.

    Sets request.state.auth_type to 'cookie' or 'bearer', and stores csrf_token in request.state if cookie.
    """
    session_cookie = request.cookies.get(COOKIE_SESSION_NAME)

    if session_cookie:
        operator, csrf_token = validate_session(session_cookie)
        if operator:
            request.state.auth_type = "cookie"
            request.state.csrf_token = csrf_token
            return operator

    # Fallback to internal service bearer token
    if authorization:
        parts = authorization.strip().split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            if secrets.compare_digest(parts[1], settings.api_bearer_token):
                request.state.auth_type = "bearer"
                request.state.csrf_token = None
                return SYSTEM_OPERATOR

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Operator authentication required.",
        headers={"WWW-Authenticate": "Bearer, Cookie"},
    )


def verify_csrf_token(
    request: Request,
    operator: OperatorPublicInfo = Depends(get_current_operator),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> None:
    """Enforce CSRF token verification on state-changing requests authenticated via session cookie."""
    if getattr(request.state, "auth_type", None) == "cookie":
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            expected_csrf = getattr(request.state, "csrf_token", None)
            if not x_csrf_token or not expected_csrf or not secrets.compare_digest(x_csrf_token, expected_csrf):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid or missing CSRF token.",
                )


def require_operator(
    operator: OperatorPublicInfo = Depends(get_current_operator),
    _: None = Depends(verify_csrf_token),
) -> OperatorPublicInfo:
    """Composite dependency verifying both operator authentication and CSRF token when applicable."""
    return operator
