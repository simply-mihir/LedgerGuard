"""Point-in-time recovery drill on a throwaway PostgreSQL (the dev databases are never touched).

Sequence, all inside one ``postgres:17-alpine`` container with continuous WAL archiving:

1. real ledger migrations, then a physical base backup (``pg_basebackup``);
2. real postings after the backup (these exist only in archived WAL);
3. ``pg_create_restore_point('before_disaster')``;
4. a simulated operator error (``DROP TABLE journal_lines``) plus one more committed write;
5. recovery of a *second* instance from the base backup + archived WAL to the named restore point.

The drill proves that a destructive mistake is undone by replaying WAL to just before it: the restored
ledger has the post-backup postings, not the disaster and not later writes, and its hash chain verifies.

Not covered: archiving to remote storage, retention/expiry of archives, backup encryption, and recovery
time at production data volume.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from uuid import uuid4

import psycopg

from ledgerguard.audit.journal_chain import verify_journal_chain
from ledgerguard.db.migrator import apply_migrations
from ledgerguard.domain.money import AmountPaise
from ledgerguard.faults.disk_full import ADMIN, ADMIN_PW, IMAGE, REPO_ROOT, docker_available
from ledgerguard.participant.account_service import create_ledger_account
from ledgerguard.participant.posting_service import simulate_funding

__all__ = ["PitrDrill", "PitrResult", "docker_available", "run_pitr_drill"]

DB_NAME = "ledger1_pitr"  # "ledger1" prefix so the chain's canonical ledger id is ledger-1
RESTORE_POINT = "before_disaster"
RESTORE_PORT = 5433


@dataclass(frozen=True)
class PitrResult:
    journals_before_disaster: int
    disaster_destroyed_primary_table: bool
    restored_journals: int
    restored_has_post_backup_postings: bool
    restored_excludes_post_disaster_write: bool
    restored_chain_ok: bool
    wal_segments_archived: int


class PitrDrill:
    def __init__(self) -> None:
        self.name = f"lg-pitr-{uuid4().hex[:8]}"
        self.port = 0
        self.restore_host_port = 0

    def url(self, port: int | None = None, user: str = ADMIN, password: str = ADMIN_PW, db: str = DB_NAME) -> str:
        return f"postgresql://{user}:{password}@127.0.0.1:{port or self.port}/{db}"

    def _exec(self, *args: str, user: str = "postgres") -> str:
        r = subprocess.run(["docker", "exec", "-u", user, self.name, *args], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"{' '.join(args)} failed: {r.stderr.strip() or r.stdout.strip()}")
        return r.stdout

    def __enter__(self) -> PitrDrill:
        subprocess.run([
            "docker", "run", "-d", "--rm", "--name", self.name,
            "-e", f"POSTGRES_USER={ADMIN}", "-e", f"POSTGRES_PASSWORD={ADMIN_PW}", "-e", "POSTGRES_DB=postgres",
            "-p", "127.0.0.1::5432", "-p", f"127.0.0.1::{RESTORE_PORT}",
            "--tmpfs", "/archive:rw,uid=70,gid=70,mode=0700",
            "--tmpfs", "/backup:rw,size=512m,uid=70,gid=70,mode=0700",
            "-v", f"{REPO_ROOT / 'docker/init-roles.sql'}:/docker-entrypoint-initdb.d/01-init-roles.sql:ro",
            IMAGE, "postgres", "-c", "archive_mode=on",
            "-c", "archive_command=test ! -f /archive/%f && cp %p /archive/%f",
        ], check=True, capture_output=True)
        try:
            self.port = self._host_port(5432)
            self.restore_host_port = self._host_port(RESTORE_PORT)
            self._wait_ready(self.port)
            with psycopg.connect(self.url(db="postgres"), autocommit=True) as c:
                c.execute(f"CREATE DATABASE {DB_NAME}")
            apply_migrations(self.url(), Path(REPO_ROOT / "migrations/ledger"))
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None,
                 tb: TracebackType | None) -> None:
        subprocess.run(["docker", "rm", "-f", self.name], capture_output=True)

    def _host_port(self, container_port: int) -> int:
        out = subprocess.run(["docker", "port", self.name, f"{container_port}/tcp"], check=True,
                             capture_output=True, text=True).stdout.splitlines()[0]
        return int(out.rsplit(":", 1)[1])

    def _wait_ready(self, port: int, timeout_s: int = 90) -> None:
        end = time.monotonic() + timeout_s
        while time.monotonic() < end:
            try:
                with psycopg.connect(self.url(port, db="postgres"), connect_timeout=2) as c:
                    c.execute("SELECT 1")
                time.sleep(1.5)  # the image restarts the server once after init scripts
                with psycopg.connect(self.url(port, db="postgres"), connect_timeout=2) as c:
                    c.execute("SELECT 1")
                return
            except psycopg.Error:
                time.sleep(0.5)
        raise RuntimeError("throwaway postgres did not become ready")

    # -- drill steps ---------------------------------------------------------------------------------

    def base_backup(self) -> None:
        self._exec("pg_basebackup", "-h", "/var/run/postgresql", "-U", ADMIN, "-D", "/backup/base",
                   "-X", "none", "-c", "fast")

    def archived_segments(self) -> int:
        return int(self._exec("sh", "-c", "ls /archive | grep -v history | wc -l").strip())

    def switch_wal_and_wait_for_archive(self, timeout_s: int = 60) -> None:
        with psycopg.connect(self.url(db="postgres"), autocommit=True) as c:
            before = c.execute("SELECT archived_count FROM pg_stat_archiver").fetchone()[0]  # type: ignore[index]
            c.execute("SELECT pg_switch_wal()")
            end = time.monotonic() + timeout_s
            while time.monotonic() < end:
                row = c.execute("SELECT archived_count, failed_count FROM pg_stat_archiver").fetchone()
                assert row is not None
                if row[0] > before:
                    return
                time.sleep(0.5)
        raise RuntimeError("WAL segment was not archived in time")

    def recover_to_restore_point(self, name: str = RESTORE_POINT, timeout_s: int = 120) -> int:
        """Start a second instance from the base backup, replay archived WAL to ``name``, return its host port."""
        self._exec("sh", "-c",
                   "printf \"%s\\n\" "
                   f"\"restore_command = 'cp /archive/%f %p'\" "
                   f"\"recovery_target_name = '{name}'\" "
                   "\"recovery_target_action = 'promote'\" "
                   ">> /backup/base/postgresql.auto.conf && touch /backup/base/recovery.signal "
                   "&& chmod 700 /backup/base")
        self._exec("pg_ctl", "-D", "/backup/base", "-o", f"-p {RESTORE_PORT}", "-l", "/backup/restore.log",
                   "-w", "-t", str(timeout_s), "start")
        end = time.monotonic() + timeout_s
        while time.monotonic() < end:
            try:
                with psycopg.connect(self.url(self.restore_host_port, db="postgres"), connect_timeout=2) as c:
                    if not c.execute("SELECT pg_is_in_recovery()").fetchone()[0]:  # type: ignore[index]
                        return self.restore_host_port
            except psycopg.Error:
                pass
            time.sleep(0.5)
        raise RuntimeError("recovery did not finish: " + self._exec("tail", "-20", "/backup/restore.log"))


def run_pitr_drill() -> PitrResult:
    with PitrDrill() as pg:
        app = pg.url(user="ledgerguard_app", password="ledgerguard_app_secret")
        pg.base_backup()

        # Real postings after the backup: present only in archived WAL.
        for _ in range(5):
            acct = create_ledger_account(app).account_id
            simulate_funding(app, acct, AmountPaise(10_000))
        with psycopg.connect(pg.url(), autocommit=True) as c:
            journals = int(c.execute("SELECT count(*) FROM journal_headers").fetchone()[0])  # type: ignore[index]
            c.execute("SELECT pg_create_restore_point(%s)", (RESTORE_POINT,))
            # The disaster, and a later write that recovery must also leave out.
            c.execute("DROP TABLE journal_lines CASCADE")
            c.execute("CREATE TABLE after_disaster_marker (id int)")
        pg.switch_wal_and_wait_for_archive()

        with psycopg.connect(pg.url()) as c:
            destroyed = c.execute("SELECT to_regclass('journal_lines')").fetchone()[0] is None  # type: ignore[index]

        port = pg.recover_to_restore_point()
        with psycopg.connect(pg.url(port)) as c:
            restored = int(c.execute("SELECT count(*) FROM journal_headers").fetchone()[0])  # type: ignore[index]
            lines = c.execute("SELECT to_regclass('journal_lines')").fetchone()[0]  # type: ignore[index]
            marker = c.execute("SELECT to_regclass('after_disaster_marker')").fetchone()[0]  # type: ignore[index]
        chain = verify_journal_chain(pg.url(port), "ledger-1")
        return PitrResult(
            journals_before_disaster=journals,
            disaster_destroyed_primary_table=destroyed,
            restored_journals=restored,
            restored_has_post_backup_postings=restored == journals and journals > 0 and lines is not None,
            restored_excludes_post_disaster_write=marker is None,
            restored_chain_ok=chain.status == "PASS" and chain.entries_checked == restored,
            wal_segments_archived=pg.archived_segments(),
        )
