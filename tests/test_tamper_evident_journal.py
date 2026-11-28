"""Tests for Stage 4 tamper-evident SHA-256 journal hash chains and Merkle checkpoints."""

from __future__ import annotations

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest

from ledgerguard.audit import (
    create_journal_checkpoint,
    verify_all_ledgers,
    verify_journal_chain,
    verify_journal_checkpoint,
)
from ledgerguard.config import settings
from ledgerguard.domain.money import AmountPaise
from ledgerguard.participant.account_service import create_ledger_account
from ledgerguard.participant.posting_service import simulate_funding


@pytest.mark.integration
def test_journal_chain_valid_under_concurrent_postings() -> None:
    acct = create_ledger_account(settings.ledger1_db_url)

    def post_one(_: int) -> None:
        simulate_funding(settings.ledger1_db_url, acct.account_id, AmountPaise(500))

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(post_one, range(6)))

    report = verify_journal_chain(settings.ledger1_db_url, "ledger-1")
    assert report.status == "PASS"
    assert report.entries_checked >= 6
    assert report.first_broken_sequence is None


@pytest.mark.integration
def test_ordinary_app_role_cannot_alter_journal_hashes() -> None:
    with pytest.raises(psycopg.Error):
        with psycopg.connect(settings.ledger1_db_url) as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE journal_headers SET entry_hash = 'deadbeef' WHERE sequence_number = 1;")
            conn.commit()


@pytest.mark.integration
def test_merkle_checkpoint_creation_and_verification() -> None:
    acct = create_ledger_account(settings.ledger1_db_url)
    simulate_funding(settings.ledger1_db_url, acct.account_id, AmountPaise(1000))

    cp = create_journal_checkpoint(
        settings.ledger1_db_url,
        settings.coordinator_db_url,
        "ledger-1",
    )
    assert cp.leaf_count >= 1
    assert cp.attested_in_coordinator is True

    ver = verify_journal_checkpoint(
        settings.ledger1_db_url,
        settings.coordinator_db_url,
        "ledger-1",
        checkpoint_id=cp.checkpoint_id,
    )
    assert ver.status == "PASS"
    assert ver.observed_merkle_root == cp.merkle_root
    assert ver.attested_merkle_root == cp.merkle_root


@pytest.mark.integration
def test_cli_verify_all_ledgers() -> None:
    res = subprocess.run(
        [sys.executable, "-m", "ledgerguard.cli", "verify-all-ledgers"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res.returncode == 0
    payload = json.loads(res.stdout)
    assert payload["status"] == "PASS"
    assert payload["ledgers"]["ledger-1"]["status"] == "PASS"
    assert payload["ledgers"]["ledger-2"]["status"] == "PASS"


@pytest.mark.integration
def test_tamper_detection_on_isolated_temp_db() -> None:
    """Create a disposable database, tamper with entry #2 as admin, and verify exact detection."""
    admin_base = settings.ledger1_admin_db_url.rsplit("/", 1)[0]
    tmp_db = "ledgerguard_tamper_test"
    tmp_admin_url = f"{admin_base}/{tmp_db}"

    with psycopg.connect(f"{admin_base}/postgres", autocommit=True) as conn:
        conn.execute(f"DROP DATABASE IF EXISTS {tmp_db};")
        conn.execute(f"CREATE DATABASE {tmp_db};")

    try:
        from pathlib import Path

        from ledgerguard.db.migrator import apply_migrations

        mig_dir = Path(__file__).parent.parent / "migrations" / "ledger"
        apply_migrations(tmp_admin_url, mig_dir)

        acct = create_ledger_account(tmp_admin_url)
        simulate_funding(tmp_admin_url, acct.account_id, AmountPaise(1000))
        simulate_funding(tmp_admin_url, acct.account_id, AmountPaise(2000))
        simulate_funding(tmp_admin_url, acct.account_id, AmountPaise(3000))

        ok = verify_journal_chain(tmp_admin_url, tmp_db)
        assert ok.status == "PASS"
        assert ok.entries_checked == 3

        # Simulate privileged offline tampering of entry #2
        with psycopg.connect(tmp_admin_url) as conn:
            with conn.cursor() as cur:
                cur.execute("ALTER TABLE journal_lines DISABLE TRIGGER trg_immutable_journal_lines_mutation;")
                cur.execute(
                    """
                    UPDATE journal_lines
                    SET amount_minor = amount_minor + 1
                    WHERE journal_id = (SELECT journal_id FROM journal_headers WHERE sequence_number = 2);
                    """
                )
                cur.execute("ALTER TABLE journal_lines ENABLE TRIGGER trg_immutable_journal_lines_mutation;")
            conn.commit()

        bad = verify_journal_chain(tmp_admin_url, tmp_db)
        assert bad.status == "FAIL"
        assert bad.first_broken_sequence == 2
        assert bad.expected_hash is not None
        assert bad.observed_hash is not None
        assert bad.expected_hash != bad.observed_hash
    finally:
        with psycopg.connect(f"{admin_base}/postgres", autocommit=True) as conn:
            conn.execute(f"DROP DATABASE IF EXISTS {tmp_db} WITH (FORCE);")


@pytest.mark.integration
def test_verify_all_ledgers_reports_incomplete_when_unreachable() -> None:
    res = verify_all_ledgers(
        ledger1_db_url=settings.ledger1_db_url,
        ledger2_db_url="postgresql://ledgerguard_app:ledgerguard_app_secret@127.0.0.1:59998/ledger2_db",
    )
    assert res["status"] == "INCOMPLETE"
    assert res["ledgers"]["ledger-2"]["status"] == "INCOMPLETE"
