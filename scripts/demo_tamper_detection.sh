#!/usr/bin/env bash
set -euo pipefail

echo "=== LedgerGuard Stage 4: Tamper-Evident Journal Detection Demo ==="
uv run python - <<'PY'
import json
from pathlib import Path
import psycopg
from ledgerguard.audit import verify_journal_chain
from ledgerguard.config import settings
from ledgerguard.db.migrator import apply_migrations
from ledgerguard.domain.money import AmountPaise
from ledgerguard.participant.account_service import create_ledger_account
from ledgerguard.participant.posting_service import simulate_funding
from ledgerguard.participant.reconciliation_service import run_local_reconciliation

admin_base = settings.ledger1_admin_db_url.rsplit("/", 1)[0]
tmp_db = "ledgerguard_tamper_demo"
tmp_url = f"{admin_base}/{tmp_db}"

with psycopg.connect(f"{admin_base}/postgres", autocommit=True) as conn:
    conn.execute(f"DROP DATABASE IF EXISTS {tmp_db};")
    conn.execute(f"CREATE DATABASE {tmp_db};")

try:
    apply_migrations(tmp_url, Path("migrations/ledger"))
    acct = create_ledger_account(tmp_url)
    for amt in (1000, 2000, 3000):
        simulate_funding(tmp_url, acct.account_id, AmountPaise(amt))

    print("\n[1] Verifying intact journal chain...")
    ok = verify_journal_chain(tmp_url, tmp_db)
    print(json.dumps(ok.model_dump(), indent=2))
    assert ok.status == "PASS"

    print("\n[2] Simulating privileged offline tampering of entry #2 (balanced debit+credit edit)...")
    with psycopg.connect(tmp_url) as conn:
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE journal_lines DISABLE TRIGGER trg_immutable_journal_lines_mutation;")
            cur.execute(
                """
                UPDATE journal_lines
                SET amount_minor = amount_minor + 500
                WHERE journal_id = (SELECT journal_id FROM journal_headers WHERE sequence_number = 2);
                """
            )
            cur.execute("ALTER TABLE journal_lines ENABLE TRIGGER trg_immutable_journal_lines_mutation;")
        conn.commit()

    print("\n[3] Running local reconciliation (debits still equal credits, showing why hash verification is a distinct control)...")
    recon = run_local_reconciliation(tmp_url)
    print(f"Reconciliation status: {recon.status} (findings={len(recon.findings)})")

    print("\n[4] Running cryptographic journal chain verification...")
    bad = verify_journal_chain(tmp_url, tmp_db)
    print(json.dumps(bad.model_dump(), indent=2))
    assert bad.status == "FAIL"
    assert bad.first_broken_sequence == 2
    print(f"\nSUCCESS: Tamper detected at sequence {bad.first_broken_sequence}!")
finally:
    with psycopg.connect(f"{admin_base}/postgres", autocommit=True) as conn:
        conn.execute(f"DROP DATABASE IF EXISTS {tmp_db} WITH (FORCE);")
PY
