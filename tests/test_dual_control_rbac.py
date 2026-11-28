"""Tests for Stage 9 four-eyes dual-control approvals and RBAC enforcement."""

from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from ledgerguard.api.app import app
from ledgerguard.approval import (
    ApprovalAuthorizationError,
    ApprovalStateError,
    SensitiveAction,
    approve_request,
    create_approval_request,
    execute_approved_request,
    reject_request,
)
from ledgerguard.config import settings


@pytest.mark.integration
def test_self_approval_and_readonly_roles_rejected() -> None:
    # VIEWER and AUDITOR cannot initiate state-changing actions
    for role in ("VIEWER", "AUDITOR"):
        with pytest.raises(ApprovalAuthorizationError):
            create_approval_request(
                settings.coordinator_db_url,
                action_type=SensitiveAction.HIGH_VALUE_TRANSFER,
                payload={"amount_minor": 500_000},
                initiator_id="viewer-1",
                initiator_role=role,
            )

    req = create_approval_request(
        settings.coordinator_db_url,
        action_type=SensitiveAction.HIGH_VALUE_TRANSFER,
        payload={"amount_minor": 500_000},
        initiator_id="op-alice",
        initiator_role="OPERATOR",
    )
    rid = UUID(str(req["request_id"]))

    # Self-approval rejected
    with pytest.raises(ApprovalAuthorizationError, match="Self-approval"):
        approve_request(
            settings.coordinator_db_url,
            request_id=rid,
            approver_id="op-alice",
            approver_role="ADMIN",
            mfa_verified=True,
        )

    # Missing MFA rejected
    with pytest.raises(ApprovalAuthorizationError, match="MFA"):
        approve_request(
            settings.coordinator_db_url,
            request_id=rid,
            approver_id="app-bob",
            approver_role="APPROVER",
            mfa_verified=False,
        )


@pytest.mark.integration
def test_payload_tampering_and_replay_rejected() -> None:
    req = create_approval_request(
        settings.coordinator_db_url,
        action_type=SensitiveAction.CHAOS_EXPERIMENT,
        payload={"seed": 42, "ops": 10},
        initiator_id="op-alice",
        initiator_role="OPERATOR",
    )
    rid = UUID(str(req["request_id"]))

    approve_request(
        settings.coordinator_db_url,
        request_id=rid,
        approver_id="app-bob",
        approver_role="APPROVER",
        mfa_verified=True,
        auth_age_seconds=10,
    )

    # Tampered payload rejected
    with pytest.raises(ApprovalStateError, match="tampering"):
        execute_approved_request(
            settings.coordinator_db_url,
            request_id=rid,
            executor_id="op-alice",
            executor_role="OPERATOR",
            expected_payload={"seed": 42, "ops": 9999},
        )

    # Valid execution succeeds once, second execution is idempotent duplicate_ignored=True
    res1 = execute_approved_request(
        settings.coordinator_db_url,
        request_id=rid,
        executor_id="op-alice",
        executor_role="OPERATOR",
        expected_payload={"seed": 42, "ops": 10},
    )
    assert res1["duplicate_ignored"] is False
    res2 = execute_approved_request(
        settings.coordinator_db_url,
        request_id=rid,
        executor_id="op-alice",
        executor_role="OPERATOR",
    )
    assert res2["duplicate_ignored"] is True


@pytest.mark.integration
def test_rejected_and_expired_requests_cannot_execute() -> None:
    req1 = create_approval_request(
        settings.coordinator_db_url,
        action_type=SensitiveAction.ROLE_CHANGE,
        payload={"target": "user-1", "role": "ADMIN"},
        initiator_id="op-1",
        initiator_role="OPERATOR",
    )
    rid1 = UUID(str(req1["request_id"]))
    reject_request(settings.coordinator_db_url, request_id=rid1, actor_id="app-1", actor_role="APPROVER")
    with pytest.raises(ApprovalStateError):
        execute_approved_request(
            settings.coordinator_db_url, request_id=rid1, executor_id="op-1", executor_role="OPERATOR"
        )

    # Expired request
    req2 = create_approval_request(
        settings.coordinator_db_url,
        action_type=SensitiveAction.TOTP_RESET,
        payload={"target": "user-2"},
        initiator_id="op-1",
        initiator_role="OPERATOR",
        ttl_seconds=-1,
    )
    rid2 = UUID(str(req2["request_id"]))
    with pytest.raises(ApprovalStateError, match="expired"):
        approve_request(
            settings.coordinator_db_url,
            request_id=rid2,
            approver_id="app-1",
            approver_role="APPROVER",
            mfa_verified=True,
        )


@pytest.mark.integration
def test_approval_api_end_to_end() -> None:
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {settings.api_bearer_token}"}
    res = client.post(
        "/v1/operator/approvals",
        headers=headers,
        json={
            "action_type": "MANUAL_RECOVERY_OVERRIDE",
            "payload": {"transfer_id": "tx-99"},
            "initiator_id": "op-1",
            "initiator_role": "OPERATOR",
        },
    )
    assert res.status_code == 200
    rid = res.json()["request_id"]

    # Self-approval returns 403
    self_res = client.post(
        f"/v1/operator/approvals/{rid}/approve",
        headers=headers,
        json={"approver_id": "op-1", "approver_role": "ADMIN", "mfa_verified": True},
    )
    assert self_res.status_code == 403
