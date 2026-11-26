"""Four-eyes dual-control approval service and RBAC policy enforcement."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from ledgerguard.db.pool import get_db_connection
from ledgerguard.domain.idempotency import compute_payload_hash


class OperatorRole(StrEnum):
    """Supported RBAC operator roles."""

    VIEWER = "VIEWER"
    OPERATOR = "OPERATOR"
    APPROVER = "APPROVER"
    AUDITOR = "AUDITOR"
    ADMIN = "ADMIN"


class SensitiveAction(StrEnum):
    """Actions requiring four-eyes dual control."""

    HIGH_VALUE_TRANSFER = "HIGH_VALUE_TRANSFER"
    CHARGEBACK_APPROVAL = "CHARGEBACK_APPROVAL"
    MANUAL_RECOVERY_OVERRIDE = "MANUAL_RECOVERY_OVERRIDE"
    CHAOS_EXPERIMENT = "CHAOS_EXPERIMENT"
    TAMPER_FIXTURE = "TAMPER_FIXTURE"
    ROLE_CHANGE = "ROLE_CHANGE"
    TOTP_RESET = "TOTP_RESET"
    DESTRUCTIVE_ADMIN_ACTION = "DESTRUCTIVE_ADMIN_ACTION"


class ApprovalState(StrEnum):
    """Approval request lifecycle states."""

    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"


class ApprovalAuthorizationError(Exception):
    """Raised when RBAC, self-approval, MFA, or recent-auth checks fail."""


class ApprovalStateError(Exception):
    """Raised on invalid state, expiry, payload tampering, or replay."""


_STATE_CHANGING_ROLES = {OperatorRole.OPERATOR, OperatorRole.APPROVER, OperatorRole.ADMIN}
_APPROVER_ROLES = {OperatorRole.APPROVER, OperatorRole.ADMIN}


def require_state_changing_role(role: str) -> OperatorRole:
    """Reject VIEWER and AUDITOR (reporter) roles from performing state-changing actions."""
    r = OperatorRole(role)
    if r not in _STATE_CHANGING_ROLES:
        raise ApprovalAuthorizationError(f"Role {r.value} is read-only and cannot perform state-changing actions.")
    return r


def create_approval_request(
    coord_db_url: str,
    *,
    action_type: SensitiveAction,
    payload: dict[str, Any],
    initiator_id: str,
    initiator_role: str,
    ttl_seconds: int = 900,
    submit_immediately: bool = True,
) -> dict[str, Any]:
    """Create a dual-control approval request with an immutable SHA-256 payload hash."""
    role = require_state_changing_role(initiator_role)
    req_id = uuid4()
    payload_hash = compute_payload_hash(payload)
    state = ApprovalState.PENDING_APPROVAL if submit_immediately else ApprovalState.DRAFT
    expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)

    with get_db_connection(coord_db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO approval_requests (
                    request_id, action_type, state, payload, payload_hash,
                    initiator_id, initiator_role, expires_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *;
                """,
                (
                    req_id,
                    action_type.value,
                    state.value,
                    Jsonb(payload),
                    payload_hash,
                    initiator_id,
                    role.value,
                    expires_at,
                ),
            )
            row = cur.fetchone()
            cur.execute(
                """
                INSERT INTO approval_events (
                    request_id, from_state, to_state, actor_id, actor_role, evidence
                ) VALUES (%s, NULL, %s, %s, %s, %s);
                """,
                (req_id, state.value, initiator_id, role.value, Jsonb({"payload_hash": payload_hash})),
            )
        conn.commit()
    assert row is not None
    return dict(row)


def approve_request(
    coord_db_url: str,
    *,
    request_id: UUID,
    approver_id: str,
    approver_role: str,
    mfa_verified: bool,
    auth_age_seconds: int = 0,
    max_auth_age_seconds: int = 900,
) -> dict[str, Any]:
    """Approve a pending dual-control request with strict separation of duties, MFA, and recent-auth checks."""
    role = OperatorRole(approver_role)
    if role not in _APPROVER_ROLES:
        raise ApprovalAuthorizationError(f"Role {role.value} is not permitted to approve sensitive actions.")
    if not mfa_verified:
        raise ApprovalAuthorizationError("MFA verification is required for APPROVER and ADMIN roles.")
    if auth_age_seconds > max_auth_age_seconds:
        raise ApprovalAuthorizationError("Recent authentication required before approving sensitive actions.")

    with get_db_connection(coord_db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM approval_requests WHERE request_id = %s FOR UPDATE;", (request_id,))
            req = cur.fetchone()
            if not req:
                raise ValueError(f"Approval request {request_id} not found.")

            if str(req["initiator_id"]) == approver_id:
                raise ApprovalAuthorizationError("Self-approval is prohibited: initiator cannot approve own request.")

            cur_state = ApprovalState(str(req["state"]))
            if cur_state != ApprovalState.PENDING_APPROVAL:
                raise ApprovalStateError(f"Request is in state {cur_state.value}, not PENDING_APPROVAL.")

            if datetime.now(UTC) > req["expires_at"].astimezone(UTC):
                cur.execute(
                    "UPDATE approval_requests SET state = 'EXPIRED', updated_at = NOW() WHERE request_id = %s;",
                    (request_id,),
                )
                cur.execute(
                    """
                    INSERT INTO approval_events (request_id, from_state, to_state, actor_id, actor_role, evidence)
                    VALUES (%s, 'PENDING_APPROVAL', 'EXPIRED', %s, %s, %s);
                    """,
                    (request_id, approver_id, role.value, Jsonb({"reason": "expired_before_approval"})),
                )
                conn.commit()
                raise ApprovalStateError("Approval request has expired.")

            # Verify payload has not been altered since submission
            recomputed_hash = compute_payload_hash(dict(req["payload"]))
            if recomputed_hash != req["payload_hash"]:
                raise ApprovalStateError("Payload hash mismatch: request payload tampered after submission.")

            cur.execute(
                """
                UPDATE approval_requests
                SET state = 'APPROVED', approver_id = %s, approver_role = %s, updated_at = NOW()
                WHERE request_id = %s
                RETURNING *;
                """,
                (approver_id, role.value, request_id),
            )
            updated = cur.fetchone()
            cur.execute(
                """
                INSERT INTO approval_events (request_id, from_state, to_state, actor_id, actor_role, evidence)
                VALUES (%s, 'PENDING_APPROVAL', 'APPROVED', %s, %s, %s);
                """,
                (request_id, approver_id, role.value, Jsonb({"payload_hash": recomputed_hash, "mfa_verified": True})),
            )
        conn.commit()
    assert updated is not None
    return dict(updated)


def reject_request(
    coord_db_url: str,
    *,
    request_id: UUID,
    actor_id: str,
    actor_role: str,
    reason: str = "rejected_by_approver",
) -> dict[str, Any]:
    """Reject a pending approval request."""
    role = OperatorRole(actor_role)
    if role not in _APPROVER_ROLES:
        raise ApprovalAuthorizationError(f"Role {role.value} cannot reject approval requests.")
    with get_db_connection(coord_db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM approval_requests WHERE request_id = %s FOR UPDATE;", (request_id,))
            req = cur.fetchone()
            if not req:
                raise ValueError(f"Approval request {request_id} not found.")
            if req["state"] != ApprovalState.PENDING_APPROVAL.value:
                raise ApprovalStateError(f"Cannot reject request in state {req['state']}.")
            cur.execute(
                """
                UPDATE approval_requests
                SET state = 'REJECTED', approver_id = %s, approver_role = %s, updated_at = NOW()
                WHERE request_id = %s
                RETURNING *;
                """,
                (actor_id, role.value, request_id),
            )
            updated = cur.fetchone()
            cur.execute(
                """
                INSERT INTO approval_events (request_id, from_state, to_state, actor_id, actor_role, evidence)
                VALUES (%s, 'PENDING_APPROVAL', 'REJECTED', %s, %s, %s);
                """,
                (request_id, actor_id, role.value, Jsonb({"reason": reason})),
            )
        conn.commit()
    assert updated is not None
    return dict(updated)


def execute_approved_request(
    coord_db_url: str,
    *,
    request_id: UUID,
    executor_id: str,
    executor_role: str,
    expected_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Idempotently execute an APPROVED request after verifying payload hash and expiry."""
    role = require_state_changing_role(executor_role)
    with get_db_connection(coord_db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM approval_requests WHERE request_id = %s FOR UPDATE;", (request_id,))
            req = cur.fetchone()
            if not req:
                raise ValueError(f"Approval request {request_id} not found.")

            cur_state = ApprovalState(str(req["state"]))
            if cur_state == ApprovalState.EXECUTED:
                return {
                    "request_id": str(request_id),
                    "state": "EXECUTED",
                    "duplicate_ignored": True,
                    "execution_result": req["execution_result"],
                }
            if cur_state != ApprovalState.APPROVED:
                raise ApprovalStateError(f"Request cannot execute from state {cur_state.value}.")

            if datetime.now(UTC) > req["expires_at"].astimezone(UTC):
                cur.execute(
                    "UPDATE approval_requests SET state = 'EXPIRED', updated_at = NOW() WHERE request_id = %s;",
                    (request_id,),
                )
                conn.commit()
                raise ApprovalStateError("Approved request has expired before execution.")

            stored_hash = str(req["payload_hash"])
            if compute_payload_hash(dict(req["payload"])) != stored_hash:
                raise ApprovalStateError("Stored payload failed integrity check against approved hash.")
            if expected_payload is not None and compute_payload_hash(expected_payload) != stored_hash:
                raise ApprovalStateError("Payload tampering detected: execution payload does not match approved hash.")

            result = {"action_type": req["action_type"], "executed_by": executor_id, "status": "COMPLETED"}
            cur.execute(
                """
                UPDATE approval_requests
                SET state = 'EXECUTED', executed_at = NOW(), execution_result = %s, updated_at = NOW()
                WHERE request_id = %s
                RETURNING *;
                """,
                (Jsonb(result), request_id),
            )
            cur.execute(
                """
                INSERT INTO approval_events (request_id, from_state, to_state, actor_id, actor_role, evidence)
                VALUES (%s, 'APPROVED', 'EXECUTED', %s, %s, %s);
                """,
                (request_id, executor_id, role.value, Jsonb(result)),
            )
        conn.commit()
    return {
        "request_id": str(request_id),
        "state": "EXECUTED",
        "duplicate_ignored": False,
        "execution_result": result,
    }


def list_approval_requests(coord_db_url: str, limit: int = 50) -> list[dict[str, Any]]:
    """List approval requests ordered newest first."""
    with get_db_connection(coord_db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM approval_requests ORDER BY created_at DESC LIMIT %s;", (limit,))
            return [dict(r) for r in cur.fetchall()]


def export_approval_audit(coord_db_url: str) -> list[dict[str, Any]]:
    """Export immutable approval audit timeline."""
    with get_db_connection(coord_db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM approval_events ORDER BY created_at ASC;")
            return [dict(r) for r in cur.fetchall()]
