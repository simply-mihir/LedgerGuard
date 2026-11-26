"""Four-eyes dual-control approval workflow and RBAC enforcement."""

from ledgerguard.approval.service import (
    ApprovalAuthorizationError,
    ApprovalState,
    ApprovalStateError,
    OperatorRole,
    SensitiveAction,
    approve_request,
    create_approval_request,
    execute_approved_request,
    export_approval_audit,
    list_approval_requests,
    reject_request,
    require_state_changing_role,
)

__all__ = [
    "ApprovalAuthorizationError",
    "ApprovalState",
    "ApprovalStateError",
    "OperatorRole",
    "SensitiveAction",
    "approve_request",
    "create_approval_request",
    "execute_approved_request",
    "export_approval_audit",
    "list_approval_requests",
    "reject_request",
    "require_state_changing_role",
]
