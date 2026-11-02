"""Integration tests for operator console REST API endpoints."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from ledgerguard.api.app import app
from ledgerguard.config import settings

client = TestClient(app)
AUTH_HEADERS = {"Authorization": f"Bearer {settings.api_bearer_token}"}


@pytest.mark.integration
def test_operator_overview_endpoint():
    """Verify /v1/operator/overview returns reachability, account/transfer counts, and clearing sum."""
    response = client.get("/v1/operator/overview")
    assert response.status_code == 200
    data = response.json()

    assert "reachability" in data
    assert data["reachability"]["coordinator"] is True
    assert data["reachability"]["ledger-1"] is True
    assert data["reachability"]["ledger-2"] is True
    assert "total_accounts" in data
    assert "total_transfers" in data
    assert "clearing_sum" in data
    assert "fault_injection_enabled" in data


@pytest.mark.integration
def test_operator_accounts_endpoint():
    """Verify /v1/operator/accounts returns provisioned accounts with live balances."""
    response = client.get("/v1/operator/accounts")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if data:
        first = data[0]
        assert "account_id" in first
        assert "ledger_id" in first
        assert "posted_balance_minor" in first
        assert "available_balance_minor" in first
        assert "status" in first


@pytest.mark.integration
def test_operator_transfers_and_timeline_endpoint():
    """Verify /v1/operator/transfers returns transfers list and timeline returns workflow events."""
    response = client.get("/v1/operator/transfers?limit=10")
    assert response.status_code == 200
    transfers = response.json()
    assert isinstance(transfers, list)

    if transfers:
        t_id = transfers[0]["transfer_id"]
        t_resp = client.get(f"/v1/operator/transfers/{t_id}/timeline")
        assert t_resp.status_code == 200
        events = t_resp.json()
        assert isinstance(events, list)


@pytest.mark.integration
def test_operator_signature_experiment_execution():
    """Verify /v1/operator/experiments/run executes SIGNATURE_RECOVERY scenario end-to-end."""
    response = client.post(
        "/v1/operator/experiments/run",
        json={"scenario": "SIGNATURE_RECOVERY"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 200
    data = response.json()

    assert data["scenario"] == "SIGNATURE_RECOVERY"
    assert data["status"] == "SETTLED"
    assert len(data["steps"]) == 5

    phases = [s["phase"] for s in data["steps"]]
    assert phases == [
        "PREPARE",
        "DECISION_POINT",
        "FAULT_INJECTION",
        "FORWARD_RECOVERY",
        "AUDIT_VERIFICATION",
    ]

    # Verify zero residual holds
    assert data["final_accounting_state"]["alice_held"] == 0
    assert data["final_accounting_state"]["bob_posted"] == 30_000


@pytest.mark.integration
def test_operator_experiment_forbidden_in_production(monkeypatch):
    """Rule: Local fault controls are disabled in public-safe / production configuration."""
    monkeypatch.setattr(settings, "env", "production")

    response = client.post(
        "/v1/operator/experiments/run",
        json={"scenario": "SIGNATURE_RECOVERY"},
        headers=AUTH_HEADERS,
    )
    assert response.status_code == 403
    assert "disabled in production" in response.json()["detail"].lower()
