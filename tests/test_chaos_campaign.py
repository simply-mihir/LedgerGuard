"""Tests for the deterministic chaos campaign engine (Stage 2)."""

from __future__ import annotations

import psycopg
import pytest
from fastapi.testclient import TestClient

from ledgerguard.api.app import app
from ledgerguard.chaos import ChaosCampaignConfig, ChaosCampaignEngine, ChaosFaultType
from ledgerguard.config import settings


def test_chaos_schedule_is_deterministic_from_seed() -> None:
    engine = ChaosCampaignEngine()
    cfg = ChaosCampaignConfig(seed=1337, operation_count=15)
    s1 = engine.build_schedule(cfg)
    s2 = engine.build_schedule(cfg)
    assert s1 == s2


def test_chaos_all_18_fault_types_defined() -> None:
    assert len(ChaosFaultType) == 18


@pytest.mark.integration
def test_chaos_campaign_executes_and_passes_invariants() -> None:
    cfg = ChaosCampaignConfig(seed=42, operation_count=12, worker_count=4, num_accounts=6)
    report = ChaosCampaignEngine().run(cfg)
    assert report.status == "PASS"
    assert report.operations_attempted == 12
    assert report.settled_count >= 1
    assert report.recovered_count >= 1
    assert report.duplicate_messages_ignored >= 1
    assert report.reconciliation_result["status"] == "PASS"
    assert report.reconciliation_result["coverage"] == "FULL"
    assert all(inv.status == "PASS" for inv in report.invariant_results)


@pytest.mark.integration
def test_chaos_campaign_never_passes_when_db_unreachable() -> None:
    bad_url = "postgresql://ledgerguard_app:ledgerguard_app_secret@127.0.0.1:59999/ledger2_db"
    engine = ChaosCampaignEngine(
        coord_db_url=settings.coordinator_db_url,
        ledger1_db_url=settings.ledger1_db_url,
        ledger2_db_url=bad_url,
    )
    # Seeding ledger2 fails or recon fails -> must not return PASS
    with pytest.raises(psycopg.OperationalError):
        engine.run(ChaosCampaignConfig(seed=9, operation_count=4, worker_count=1, num_accounts=4))


def test_chaos_disabled_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "env", "production")
    with pytest.raises(RuntimeError, match="disabled in production"):
        ChaosCampaignEngine().run(ChaosCampaignConfig(seed=1, operation_count=2))

    client = TestClient(app)
    res = client.post(
        "/v1/operator/chaos/run",
        headers={"Authorization": f"Bearer {settings.api_bearer_token}"},
        json={"seed": 1, "operation_count": 2},
    )
    assert res.status_code == 403


@pytest.mark.integration
def test_chaos_operator_api_run_and_list() -> None:
    client = TestClient(app)
    headers = {"Authorization": f"Bearer {settings.api_bearer_token}"}
    res = client.post(
        "/v1/operator/chaos/run",
        headers=headers,
        json={"seed": 77, "operation_count": 8, "worker_count": 2, "num_accounts": 4},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "PASS"
    assert body["seed"] == 77

    list_res = client.get("/v1/operator/chaos/campaigns", headers=headers)
    assert list_res.status_code == 200
    assert any(item["campaign_id"] == body["campaign_id"] for item in list_res.json())
