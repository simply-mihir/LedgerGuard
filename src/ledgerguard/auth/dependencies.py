"""FastAPI dependencies for operator session authentication and CSRF protection."""

import secrets
from uuid import UUID, uuid5

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

_SERVICE_NAMESPACE = UUID("6f1a9d2e-5b0c-4c7e-9a41-0d3b8e6f2a10")


def _service_operator(name: str, role: str) -> OperatorPublicInfo:
    """Stable, attributable identity for a named service credential (never has MFA)."""
    return OperatorPublicInfo(
        operator_id=uuid5(_SERVICE_NAMESPACE, name),
        username=f"svc:{name}",
        email=f"{name}@service.ledgerguard.internal",
        role=role,  # type: ignore[arg-type]
        totp_enabled=False,
    )

# Roles allowed to perform state-changing actions. VIEWER and AUDITOR are read-only.
WRITE_ROLES = frozenset({"OPERATOR", "APPROVER", "ADMIN"})


def get_current_operator(
    request: Request,
    authorization: str | None = Header(default=None),
) -> OperatorPublicInfo:
    """Authenticate via HttpOnly session cookie or the internal service Bearer token.

    This is the single authentication path for the whole API. Sets request.state.auth_type
    ('cookie' | 'bearer'), request.state.operator, and request.state.csrf_token (cookie only).
    Missing or malformed credentials are 401; a well-formed but wrong bearer token is 403.
    """
    session_cookie = request.cookies.get(COOKIE_SESSION_NAME)
    if session_cookie:
        operator, csrf_token = validate_session(session_cookie)
        if operator:
            request.state.auth_type = "cookie"
            request.state.operator = operator
            request.state.csrf_token = csrf_token
            return operator

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
    presented = parts[1]
    # Compare against every credential (no early exit) to keep timing independent of which matched.
    matched: tuple[str, str] | None = None
    for name, role, token in settings.get_service_credentials():
        if secrets.compare_digest(presented, token):
            matched = (name, role)
    legacy_ok = settings.env != "production" and secrets.compare_digest(
        presented, settings.api_bearer_token
    )
    if matched is not None:
        operator = _service_operator(*matched)
        request.state.auth_type = "service"
    elif legacy_ok:
        operator = SYSTEM_OPERATOR
        request.state.auth_type = "bearer"
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or expired bearer token",
        )
    request.state.operator = operator
    request.state.csrf_token = None
    return operator


def verify_csrf_token(
    request: Request,
    operator: OperatorPublicInfo = Depends(get_current_operator),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> None:
    """Enforce CSRF token and Origin verification on state-changing requests authenticated via session cookie."""
    if getattr(request.state, "auth_type", None) == "cookie":
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            # 1. Validate complete Origin (scheme, host, port) if present
            origin = request.headers.get("origin")
            if origin:
                from ledgerguard.auth.origins import is_origin_allowed

                if not is_origin_allowed(origin, settings.get_trusted_origins()):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Cross-origin state-changing request rejected.",
                    )

            # 2. Enforce constant-time CSRF token comparison
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
    """Composite dependency verifying operator authentication and CSRF token when applicable."""
    return operator


def require_write_operator(
    operator: OperatorPublicInfo = Depends(require_operator),
) -> OperatorPublicInfo:
    """Like require_operator, but rejects read-only roles (VIEWER, AUDITOR)."""
    if operator.role not in WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role {operator.role} is read-only and cannot perform this action.",
        )
    return operator


def require_authenticated(
    request: Request,
    operator: OperatorPublicInfo = Depends(require_operator),
) -> OperatorPublicInfo:
    """Any authenticated operator may read; only WRITE_ROLES may use mutating methods."""
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and operator.role not in WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role {operator.role} is read-only and cannot perform this action.",
        )
    return operator
