"""Disposable-environment disaster recovery backup, restore, replay, and RPO/RTO measurement."""

from __future__ import annotations

import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from ledgerguard.audit import (
    create_journal_checkpoint,
    verify_journal_chain,
    verify_journal_checkpoint,
)
from ledgerguard.config import settings
from ledgerguard.coordinator.directory_service import provision_account, register_customer
from ledgerguard.coordinator.failpoints import CrashAfterCommitError, FailpointManager
from ledgerguard.coordinator.reconciliation import run_cross_ledger_reconciliation
from ledgerguard.coordinator.transfer_coordinator import submit_coordinator_transfer
from ledgerguard.db.migrator import apply_migrations
from ledgerguard.db.pool import close_all_pools
from ledgerguard.domain.money import AmountPaise
from ledgerguard.participant.posting_service import simulate_funding
from ledgerguard.worker.orchestrator import recover_pending_transfers


class DisposableEnvironmentError(Exception):
    """Raised when DR drill is invoked without explicit disposable-environment guard."""


class BackupMetadata(BaseModel):
    """Metadata recorded at backup time."""

    target_db: str
    backup_started_at: str
    backup_finished_at: str
    latest_journal_sequence: int = 0
    checkpoint_root: str | None = None
    unresolved_transfer_count: int = 0


class DisasterRecoveryReport(BaseModel):
    """Measured RPO/RTO and post-restore verification report."""

    scenario: str
    status: str  # PASS, FAIL, INCOMPLETE
    backup: BackupMetadata
    rpo_seconds: float
    rto_seconds: float
    transactions_replayed: int
    unresolved_obligations_after: int
    journal_chain_status: str
    checkpoint_status: str
    reconciliation_status: str
    data_loss_note: str
    details: dict[str, Any] = Field(default_factory=dict)


def _assert_disposable_guard(confirm_disposable: bool, db_names: list[str]) -> None:
    if not confirm_disposable:
        raise DisposableEnvironmentError("Explicit confirmation (confirm_disposable=True) is required.")
    if settings.env == "production":
        raise DisposableEnvironmentError("Disaster recovery drills are prohibited in production.")
    for name in db_names:
        if "disposable" not in name and "dr_test" not in name and "dr_demo" not in name:
            raise DisposableEnvironmentError(
                f"Refusing to destroy non-disposable database '{name}'. Name must contain 'disposable', 'dr_test', or 'dr_demo'."
            )


def _pg_dump_via_docker(container: str, user: str, db_name: str, out_file: Path) -> None:
    res = subprocess.run(
        ["docker", "exec", container, "pg_dump", "-U", user, "-Fc", db_name],
        capture_output=True,
        check=True,
    )
    out_file.write_bytes(res.stdout)


def _pg_restore_via_docker(container: str, user: str, db_name: str, dump_file: Path) -> None:
    data = dump_file.read_bytes()
    subprocess.run(
        ["docker", "exec", "-i", container, "pg_restore", "-U", user, "-d", db_name, "--no-owner"],
        input=data,
        capture_output=True,
        check=True,
    )


def _resolve_container_for_port(port: int) -> str:
    if port == 5442:
        return "ledgerguard-postgres-coordinator-1"
    if port == 5443:
        return "ledgerguard-postgres-ledger1-1"
    if port == 5444:
        return "ledgerguard-postgres-ledger2-1"
    raise DisposableEnvironmentError(f"Unsupported PostgreSQL port {port} for isolated DR drill.")


def run_disposable_dr_drill(
    *,
    scenario: str = "LEDGER1_LOSS_WITH_INFLIGHT_RECOVERY",
    confirm_disposable: bool = False,
    work_dir: Path | None = None,
) -> DisasterRecoveryReport:
    """Execute an end-to-end backup, database loss, restore, replay, and verification drill
    using isolated disposable databases inside the local Docker triad.
    """
    suffix = uuid4().hex[:6]
    coord_db = f"dr_test_coord_{suffix}"
    l1_db = f"dr_test_l1_{suffix}"
    l2_db = f"dr_test_l2_{suffix}"
    _assert_disposable_guard(confirm_disposable, [coord_db, l1_db, l2_db])

    coord_base = settings.coordinator_admin_db_url.rsplit("/", 1)[0]
    l1_base = settings.ledger1_admin_db_url.rsplit("/", 1)[0]
    l2_base = settings.ledger2_admin_db_url.rsplit("/", 1)[0]

    coord_url = f"{coord_base}/{coord_db}"
    l1_url = f"{l1_base}/{l1_db}"
    l2_url = f"{l2_base}/{l2_db}"
    ledger_urls = {"ledger-1": l1_url, "ledger-2": l2_url}

    c_port = urlparse(coord_url).port or 5442
    l1_port = urlparse(l1_url).port or 5443
    l2_port = urlparse(l2_url).port or 5444
    coord_container = _resolve_container_for_port(c_port)
    l1_container = _resolve_container_for_port(l1_port)
    _ = l2_container = _resolve_container_for_port(l2_port)

    root_dir = Path(__file__).parent.parent.parent.parent
    dump_dir = work_dir or Path("/tmp")
    dump_path = dump_dir / f"dr_{l1_db}.dump"

    for base, name in ((coord_base, coord_db), (l1_base, l1_db), (l2_base, l2_db)):
        with psycopg.connect(f"{base}/postgres", autocommit=True) as conn:
            conn.execute(f"DROP DATABASE IF EXISTS {name};")
            conn.execute(f"CREATE DATABASE {name};")

    try:
        apply_migrations(coord_url, root_dir / "migrations" / "coordinator")
        apply_migrations(l1_url, root_dir / "migrations" / "ledger")
        apply_migrations(l2_url, root_dir / "migrations" / "ledger")

        # Seed synthetic accounts & 1 settled transfer + 1 COMMITTING in-flight transfer
        c1 = register_customer(coord_url, "DR Alice", f"dr-a-{suffix}@synthetic.local")
        c2 = register_customer(coord_url, "DR Bob", f"dr-b-{suffix}@synthetic.local")
        a1 = provision_account(coord_url, ledger_urls, UUID(str(c1["customer_id"])), "ledger-1")
        a2 = provision_account(coord_url, ledger_urls, UUID(str(c2["customer_id"])), "ledger-2")
        src_id = UUID(str(a1["account_id"]))
        dst_id = UUID(str(a2["account_id"]))
        simulate_funding(l1_url, src_id, AmountPaise(50_000))

        # Settled transfer before backup
        submit_coordinator_transfer(
            coord_url,
            ledger_urls,
            idempotency_key=f"dr-settled-{suffix}",
            source_account_id=src_id,
            destination_account_id=dst_id,
            amount=AmountPaise(10_000),
        )

        # In-flight COMMITTING transfer (crash after commit before source confirm)
        inflight_id = uuid4()
        fp = FailpointManager()
        fp.set_failpoint("FAIL_AFTER_COMMIT_BEFORE_SOURCE_CONFIRM", inflight_id)
        try:
            submit_coordinator_transfer(
                coord_url,
                ledger_urls,
                idempotency_key=f"dr-inflight-{suffix}",
                source_account_id=src_id,
                destination_account_id=dst_id,
                amount=AmountPaise(5_000),
                transfer_id=inflight_id,
                failpoint_mgr=fp,
            )
        except CrashAfterCommitError:
            pass

        cp = create_journal_checkpoint(l1_url, coord_url, "ledger-1")

        # Record backup metadata
        b_start = datetime.now(UTC)
        with psycopg.connect(l1_url) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT COALESCE(MAX(sequence_number), 0) AS s FROM journal_headers;")
                r1 = cur.fetchone()
                latest_seq = int(r1["s"]) if r1 else 0
        with psycopg.connect(coord_url) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT COUNT(*) AS c FROM transfers WHERE state NOT IN ('SETTLED', 'CANCELLED');")
                r2 = cur.fetchone()
                unresolved_before = int(r2["c"]) if r2 else 0

        _pg_dump_via_docker(l1_container, "ledgerguard_admin", l1_db, dump_path)
        b_end = datetime.now(UTC)

        # Simulate catastrophic Ledger 1 database loss & restore
        t_rto_start = time.perf_counter()
        close_all_pools()
        with psycopg.connect(f"{l1_base}/postgres", autocommit=True) as conn:
            conn.execute(f"DROP DATABASE IF EXISTS {l1_db} WITH (FORCE);")
            conn.execute(f"CREATE DATABASE {l1_db};")

        _pg_restore_via_docker(l1_container, "ledgerguard_admin", l1_db, dump_path)
        apply_migrations(l1_url, root_dir / "migrations" / "ledger")
        close_all_pools()

        # Forward recovery replay of outstanding COMMITTING obligations
        recovered = recover_pending_transfers(coord_url, ledger_urls)

        # Drain & verify
        with psycopg.connect(coord_url) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT COUNT(*) AS c FROM transfers WHERE state NOT IN ('SETTLED', 'CANCELLED');")
                r3 = cur.fetchone()
                unresolved_after = int(r3["c"]) if r3 else 0

        chain_rep = verify_journal_chain(l1_url, "ledger-1")
        cp_rep = verify_journal_checkpoint(l1_url, coord_url, "ledger-1", checkpoint_id=cp.checkpoint_id)
        recon = run_cross_ledger_reconciliation(coord_url, ledger_urls, drained=True)
        rto_sec = round(time.perf_counter() - t_rto_start, 3)

        status = (
            "PASS"
            if chain_rep.status == "PASS"
            and cp_rep.status == "PASS"
            and recon.status == "PASS"
            and unresolved_after == 0
            else "FAIL"
        )

        return DisasterRecoveryReport(
            scenario=scenario,
            status=status,
            backup=BackupMetadata(
                target_db=l1_db,
                backup_started_at=b_start.isoformat(),
                backup_finished_at=b_end.isoformat(),
                latest_journal_sequence=latest_seq,
                checkpoint_root=cp.merkle_root,
                unresolved_transfer_count=unresolved_before,
            ),
            rpo_seconds=0.0,
            rto_seconds=rto_sec,
            transactions_replayed=len(recovered),
            unresolved_obligations_after=unresolved_after,
            journal_chain_status=chain_rep.status,
            checkpoint_status=cp_rep.status,
            reconciliation_status=recon.status,
            data_loss_note="Backup captured after commit; all committed obligations recovered forward (RPO=0 for this checkpoint). Post-backup uncaptured writes would have RPO > 0.",
            details={
                "coordinator_container": coord_container,
                "ledger1_container": l1_container,
                "ledger2_container": l2_container,
                "clearing_balance_sum": recon.clearing_balance_sum,
            },
        )
    finally:
        if dump_path.exists():
            dump_path.unlink(missing_ok=True)
        for base, name in ((coord_base, coord_db), (l1_base, l1_db), (l2_base, l2_db)):
            with psycopg.connect(f"{base}/postgres", autocommit=True) as conn:
                conn.execute(f"DROP DATABASE IF EXISTS {name} WITH (FORCE);")
