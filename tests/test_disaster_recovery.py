"""Tests for Stage 12 disaster recovery and restore verification."""

from __future__ import annotations

import pytest

from ledgerguard.config import settings
from ledgerguard.dr import DisposableEnvironmentError, run_disposable_dr_drill


def test_dr_drill_requires_explicit_disposable_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(DisposableEnvironmentError, match="Explicit confirmation"):
        run_disposable_dr_drill(confirm_disposable=False)

    monkeypatch.setattr(settings, "env", "production")
    with pytest.raises(DisposableEnvironmentError, match="prohibited in production"):
        run_disposable_dr_drill(confirm_disposable=True)


@pytest.mark.integration
def test_dr_drill_backup_loss_restore_replay_and_verify() -> None:
    rep = run_disposable_dr_drill(confirm_disposable=True)
    assert rep.status == "PASS"
    assert rep.journal_chain_status == "PASS"
    assert rep.checkpoint_status == "PASS"
    assert rep.reconciliation_status == "PASS"
    assert rep.unresolved_obligations_after == 0
    assert rep.transactions_replayed >= 1
    assert rep.rto_seconds > 0
