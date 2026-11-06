"""Pydantic models for operator authentication, session management, and MFA."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class OperatorPublicInfo(BaseModel):
    """Safe public representation of an authenticated operator."""

    operator_id: UUID
    username: str
    email: str
    role: Literal["OPERATOR", "ADMIN", "AUDITOR"]
    totp_enabled: bool


class OperatorLoginRequest(BaseModel):
    """Credentials submitted to initialize operator session."""

    identifier: str = Field(..., min_length=3, max_length=255, description="Username or email address")
    password: str = Field(..., min_length=8, max_length=255, description="Plaintext operator password")


class OperatorLoginResponse(BaseModel):
    """Result of initial authentication check."""

    status: Literal["SUCCESS", "MFA_REQUIRED"]
    temp_token: str | None = None
    csrf_token: str | None = None
    operator: OperatorPublicInfo | None = None
    message: str


class OperatorMfaVerifyRequest(BaseModel):
    """Second-factor verification submission."""

    temp_token: str = Field(..., description="Short-lived token received from initial login")
    code: str = Field(..., min_length=6, max_length=6, description="6-digit TOTP code")


class OperatorMfaConfirmRequest(BaseModel):
    """Confirm newly enrolled TOTP authenticator with a 6-digit code."""

    code: str = Field(..., min_length=6, max_length=6, description="6-digit verification code")


class OperatorEnrollMfaResponse(BaseModel):
    """Provisioning payload for setting up TOTP authenticator."""

    totp_secret: str
    provisioning_uri: str
    manual_entry_key: str


class OperatorSessionResponse(BaseModel):
    """Session inspection and identity state."""

    authenticated: bool
    operator: OperatorPublicInfo | None = None
    csrf_token: str | None = None


class CreateOperatorRequest(BaseModel):
    """Request to create a new operator account."""

    username: str = Field(..., min_length=3, max_length=64)
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=8, max_length=255)
    role: Literal["OPERATOR", "ADMIN", "AUDITOR"] = "OPERATOR"
    enable_totp: bool = False
