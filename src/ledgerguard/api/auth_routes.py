"""FastAPI routes for operator authentication, session management, and multi-factor setup."""

import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status

from ledgerguard.auth.dependencies import (
    COOKIE_SESSION_NAME,
    require_operator,
)
from ledgerguard.auth.models import (
    OperatorEnrollMfaResponse,
    OperatorLoginRequest,
    OperatorLoginResponse,
    OperatorMfaConfirmRequest,
    OperatorMfaVerifyRequest,
    OperatorPublicInfo,
    OperatorSessionResponse,
)
from ledgerguard.auth.service import (
    AuthenticationError,
    authenticate_operator,
    confirm_totp_enrollment,
    enroll_totp,
    revoke_session,
    validate_session,
    verify_mfa_login,
)
from ledgerguard.config import settings

auth_router = APIRouter(prefix="/v1/auth", tags=["Operator Authentication"])


def _set_session_cookie(response: Response, raw_token: str, request: Request | None = None) -> None:
    """Attach the server session identifier in a secure, HttpOnly, SameSite cookie."""
    is_secure = False
    if request:
        proto = request.headers.get("x-forwarded-proto", "").lower()
        is_secure = (proto == "https") or (request.url.scheme == "https")
    if not is_secure and settings.env not in ("local", "test"):
        is_secure = True

    response.set_cookie(
        key=COOKIE_SESSION_NAME,
        value=raw_token,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        max_age=43200,  # 12 hours absolute
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    """Clear session cookie upon logout or expiry."""
    response.delete_cookie(
        key=COOKIE_SESSION_NAME,
        path="/",
    )


@auth_router.post(
    "/login",
    response_model=OperatorLoginResponse,
    summary="Authenticate operator credentials",
)
def login(
    req: OperatorLoginRequest,
    request: Request,
    response: Response,
) -> OperatorLoginResponse:
    """Verify operator credentials.

    If MFA is enabled, returns temporary token for TOTP verification step.
    If MFA is disabled, provisions a server session with SHA-256 hash and sets HttpOnly cookie.
    Rotates session if an existing session was present.
    """
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    old_session = request.cookies.get(COOKIE_SESSION_NAME)

    try:
        login_resp, raw_session_token, _ = authenticate_operator(
            identifier=req.identifier,
            password=req.password,
            ip_address=ip_address,
            user_agent=user_agent,
            old_raw_token=old_session,
        )
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.message,
        ) from exc

    if raw_session_token:
        _set_session_cookie(response, raw_session_token, request=request)

    return login_resp


@auth_router.post(
    "/mfa/verify",
    response_model=OperatorLoginResponse,
    summary="Verify second-factor TOTP code",
)
def mfa_verify(
    req: OperatorMfaVerifyRequest,
    request: Request,
    response: Response,
) -> OperatorLoginResponse:
    """Verify 6-digit TOTP verification code from authenticator app with replay protection."""
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    old_session = request.cookies.get(COOKIE_SESSION_NAME)

    try:
        login_resp, raw_session_token, _ = verify_mfa_login(
            temp_token=req.temp_token,
            code=req.code,
            ip_address=ip_address,
            user_agent=user_agent,
            old_raw_token=old_session,
        )
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.message,
        ) from exc

    _set_session_cookie(response, raw_session_token, request=request)
    return login_resp


@auth_router.get(
    "/session",
    response_model=OperatorSessionResponse,
    summary="Inspect current operator session",
)
def get_session(request: Request) -> OperatorSessionResponse:
    """Check whether the client possesses a valid, non-expired operator session."""
    session_cookie = request.cookies.get(COOKIE_SESSION_NAME)
    if not session_cookie:
        return OperatorSessionResponse(authenticated=False)

    operator, csrf_token = validate_session(session_cookie)
    if not operator:
        return OperatorSessionResponse(authenticated=False)

    return OperatorSessionResponse(
        authenticated=True,
        operator=operator,
        csrf_token=csrf_token,
    )


@auth_router.post(
    "/logout",
    summary="Revoke active operator session",
)
def logout(
    request: Request,
    response: Response,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, str]:
    """Revoke operator session in database and delete browser cookie.

    Enforces CSRF protection on logout when authenticated via session cookie.
    """
    session_cookie = request.cookies.get(COOKIE_SESSION_NAME)
    if session_cookie:
        operator, expected_csrf = validate_session(session_cookie)
        if operator and expected_csrf:
            if not x_csrf_token or not secrets.compare_digest(x_csrf_token, expected_csrf):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Invalid or missing CSRF token on logout.",
                )
        revoke_session(session_cookie)

    _clear_session_cookie(response)
    return {"status": "REVOKED", "message": "Operator session revoked successfully."}


@auth_router.post(
    "/mfa/enroll",
    response_model=OperatorEnrollMfaResponse,
    summary="Initialize TOTP authenticator enrollment",
)
def enroll_mfa(
    operator: OperatorPublicInfo = Depends(require_operator),
) -> OperatorEnrollMfaResponse:
    """Generate a fresh TOTP secret for the active operator to scan into an authenticator."""
    secret, uri, key = enroll_totp(operator.operator_id)
    return OperatorEnrollMfaResponse(
        totp_secret=secret,
        provisioning_uri=uri,
        manual_entry_key=key,
    )


@auth_router.post(
    "/mfa/confirm",
    summary="Confirm and activate newly enrolled TOTP authenticator",
)
def confirm_mfa(
    req: OperatorMfaConfirmRequest,
    operator: OperatorPublicInfo = Depends(require_operator),
) -> dict[str, str]:
    """Validate 6-digit code against staged TOTP secret and activate MFA."""
    success = confirm_totp_enrollment(operator.operator_id, req.code)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code does not match authenticator secret.",
        )
    return {"status": "ACTIVATED", "message": "Two-factor authentication is now active on your operator account."}
