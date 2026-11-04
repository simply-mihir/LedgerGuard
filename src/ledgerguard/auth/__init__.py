"""LedgerGuard operator authentication, MFA, and session security module."""

from ledgerguard.auth.dependencies import (
    COOKIE_SESSION_NAME,
    get_current_operator,
    require_operator,
    verify_csrf_token,
)
from ledgerguard.auth.models import (
    CreateOperatorRequest,
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
    create_operator_account,
    enroll_totp,
    revoke_session,
    validate_session,
    verify_mfa_login,
)

__all__ = [
    "AuthenticationError",
    "COOKIE_SESSION_NAME",
    "CreateOperatorRequest",
    "OperatorEnrollMfaResponse",
    "OperatorLoginRequest",
    "OperatorLoginResponse",
    "OperatorMfaConfirmRequest",
    "OperatorMfaVerifyRequest",
    "OperatorPublicInfo",
    "OperatorSessionResponse",
    "authenticate_operator",
    "confirm_totp_enrollment",
    "create_operator_account",
    "enroll_totp",
    "get_current_operator",
    "require_operator",
    "revoke_session",
    "validate_session",
    "verify_csrf_token",
    "verify_mfa_login",
]
