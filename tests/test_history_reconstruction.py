"""Tests for Stage 7 as-of-time balance reconstruction and checksummed snapshots."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from ledgerguard.config import settings
from ledgerguard.domain.money import AmountPaise
from ledgerguard.history import (
    create_account_snapshot,
    reconstruct_account_balance_as_of,
    reconstruct_clearing_as_of,
)
from ledgerguard.participant.account_service import create_ledger_account
from ledgerguard.participant.posting_service import simulate_cash_out, simulate_funding


@pytest.mark.integration
def test_as_of_reconstruction_agrees_with_snapshots_and_full_replay() -> None:
    acct = create_ledger_account(settings.ledger1_db_url)
    simulate_funding(settings.ledger1_db_url, acct.account_id, AmountPaise(5_000))

    with psycopg.connect(settings.ledger1_db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT NOW();")
            row = cur.fetchone()
            assert row is not None
            t1: datetime = row[0]

    snap = create_account_snapshot(settings.ledger1_db_url, acct.account_id, "ledger-1")
    assert snap.posted_balance_minor == 5_000

    simulate_funding(settings.ledger1_db_url, acct.account_id, AmountPaise(2_000))
    simulate_cash_out(settings.ledger1_db_url, acct.account_id, AmountPaise(1_000))

    # Reconstruct at t1 (before the +2000 and -1000)
    proof_t1 = reconstruct_account_balance_as_of(settings.ledger1_db_url, acct.account_id, t1)
    assert proof_t1.posted_balance_minor == 5_000
    assert len(proof_t1.included_entries) == 1
    assert len(proof_t1.excluded_entries) == 2

    # Reconstruct at now (with snapshot + replay == full replay == 6000)
    now_ts = datetime.now(UTC) + timedelta(seconds=5)
    proof_snap = reconstruct_account_balance_as_of(
        settings.ledger1_db_url, acct.account_id, now_ts, use_snapshots=True
    )
    proof_full = reconstruct_account_balance_as_of(
        settings.ledger1_db_url, acct.account_id, now_ts, use_snapshots=False
    )
    assert proof_snap.verification_status == "VERIFIED"
    assert proof_snap.posted_balance_minor == 6_000
    assert proof_full.posted_balance_minor == 6_000
    assert proof_snap.present_posted_balance_minor == 6_000


@pytest.mark.integration
def test_as_of_rejects_timestamp_before_account_creation() -> None:
    acct = create_ledger_account(settings.ledger1_db_url)
    too_early = datetime(2020, 1, 1, tzinfo=UTC)
    with pytest.raises(ValueError, match="precedes account creation"):
        reconstruct_account_balance_as_of(settings.ledger1_db_url, acct.account_id, too_early)


@pytest.mark.integration
def test_snapshot_corruption_detected_and_falls_back_to_full_replay() -> None:
    acct = create_ledger_account(settings.ledger1_db_url)
    simulate_funding(settings.ledger1_db_url, acct.account_id, AmountPaise(4_000))
    snap = create_account_snapshot(settings.ledger1_db_url, acct.account_id, "ledger-1")

    # Simulate privileged snapshot tampering
    with psycopg.connect(settings.ledger1_admin_db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE balance_snapshots DISABLE TRIGGER trg_immutable_balance_snapshots;")
            cur.execute(
                "UPDATE balance_snapshots SET posted_balance_minor = 999999 WHERE snapshot_id = %s;",
                (snap.snapshot_id,),
            )
            cur.execute("ALTER TABLE balance_snapshots ENABLE TRIGGER trg_immutable_balance_snapshots;")
        conn.commit()

    proof = reconstruct_account_balance_as_of(
        settings.ledger1_db_url,
        acct.account_id,
        datetime.now(UTC) + timedelta(seconds=5),
        use_snapshots=True,
    )
    assert proof.verification_status == "SNAPSHOT_CORRUPTED"
    assert proof.posted_balance_minor == 4_000


@pytest.mark.integration
def test_clearing_as_of_incomplete_when_db_unreachable() -> None:
    rep = reconstruct_clearing_as_of(
        settings.ledger1_db_url,
        "postgresql://ledgerguard_app:ledgerguard_app_secret@127.0.0.1:59997/ledger2_db",
        datetime.now(UTC),
    )
    assert rep.status == "INCOMPLETE"


def test_as_of_selection_is_a_sequence_prefix_even_if_the_clock_stepped_backwards() -> None:
    """Entries 1,2,3 are stamped 10:00, 10:30, 10:10: entry 3 was written after a backwards clock step."""
    from ledgerguard.history.reconstruction import select_as_of_prefix

    def line(seq: int, minute: int, side: str, amount: int) -> dict:
        return {"journal_id": f"j{seq}", "sequence_number": seq, "operation_type": "FUNDING", "side": side,
                "amount_minor": amount, "created_at": datetime(2026, 1, 1, 10, minute, tzinfo=UTC)}

    lines = [line(1, 0, "CREDIT", 1_000), line(2, 30, "CREDIT", 500), line(3, 10, "CREDIT", 200)]
    t = datetime(2026, 1, 1, 10, 20, tzinfo=UTC)  # between entry 1 and entry 2
    included, excluded, posted = select_as_of_prefix(lines, "LIABILITY", t)
    assert [e["journal_id"] for e in included] == ["j1"]
    assert [e["journal_id"] for e in excluded] == ["j2", "j3"], "j3 is stamped before T but follows j2"
    assert posted == 1_000, "never 1,200: that balance (j1 + j3 without j2) never existed"

    # with a monotonic clock the selection is exactly the old time filter
    mono = [line(1, 0, "CREDIT", 1_000), line(2, 10, "CREDIT", 500), line(3, 30, "CREDIT", 200)]
    inc, exc, bal = select_as_of_prefix(mono, "LIABILITY", t)
    assert [e["journal_id"] for e in inc] == ["j1", "j2"] and bal == 1_500 and len(exc) == 1
