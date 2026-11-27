"""A throwaway PostgreSQL whose data tablespace lives on a tiny size-limited volume.

The dev databases are never touched. A separate ``postgres:17-alpine`` container is started with a
16 MB tmpfs mounted as a tablespace; a ledger database is created in that tablespace and migrated
with the real ledger migrations. WAL stays on the container's normal disk, so filling the tablespace
produces the recoverable failure a full data volume gives (SQLSTATE 53100 "could not extend file")
rather than a WAL PANIC.

Not covered: WAL volume exhaustion (PostgreSQL PANICs and runs crash recovery) and fsync failures,
which need block-layer fault injection that a container cannot provide portably.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path
from types import TracebackType
from uuid import uuid4

import psycopg

from ledgerguard.db.migrator import apply_migrations

REPO_ROOT = Path(__file__).resolve().parents[3]
IMAGE = "postgres:17-alpine"
TABLESPACE_MB = 16
DB_NAME = "ledger1_diskfull"  # starts with "ledger1" so the chain's canonical ledger id is ledger-1
ADMIN = "ledgerguard_admin"
ADMIN_PW = "ledgerguard_admin_secret"


def docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        subprocess.run(["docker", "image", "inspect", IMAGE], check=True, capture_output=True, timeout=20)
    except (subprocess.SubprocessError, OSError):
        return False
    return True


class SmallDiskPostgres:
    def __init__(self) -> None:
        self.name = f"lg-diskfull-{uuid4().hex[:8]}"
        self.port = 0

    def url(self, user: str = ADMIN, password: str = ADMIN_PW, db: str = DB_NAME) -> str:
        return f"postgresql://{user}:{password}@127.0.0.1:{self.port}/{db}"

    def __enter__(self) -> SmallDiskPostgres:
        subprocess.run([
            "docker", "run", "-d", "--rm", "--name", self.name,
            "-e", f"POSTGRES_USER={ADMIN}", "-e", f"POSTGRES_PASSWORD={ADMIN_PW}",
            "-e", "POSTGRES_DB=postgres",
            "-p", "127.0.0.1::5432",
            "--tmpfs", f"/mnt/smalldisk:rw,size={TABLESPACE_MB}m,uid=70,gid=70,mode=0700",
            "-v", f"{REPO_ROOT / 'docker/init-roles.sql'}:/docker-entrypoint-initdb.d/01-init-roles.sql:ro",
            IMAGE,
        ], check=True, capture_output=True)
        try:
            out = subprocess.run(["docker", "port", self.name, "5432/tcp"], check=True,
                                 capture_output=True, text=True).stdout.splitlines()[0]
            self.port = int(out.rsplit(":", 1)[1])
            self._wait_ready()
            with psycopg.connect(self.url(db="postgres"), autocommit=True) as c:
                c.execute("CREATE TABLESPACE smalldisk LOCATION '/mnt/smalldisk'")
                c.execute(f"CREATE DATABASE {DB_NAME} TABLESPACE smalldisk")
            apply_migrations(self.url(), REPO_ROOT / "migrations/ledger")
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def _wait_ready(self, timeout_s: int = 60) -> None:
        end = time.monotonic() + timeout_s
        while time.monotonic() < end:
            try:
                with psycopg.connect(self.url(db="postgres"), connect_timeout=2) as c:
                    c.execute("SELECT 1")
                # The image restarts the server once after init scripts; require two good probes.
                time.sleep(1.5)
                with psycopg.connect(self.url(db="postgres"), connect_timeout=2) as c:
                    c.execute("SELECT 1")
                return
            except psycopg.Error:
                time.sleep(0.5)
        raise RuntimeError("throwaway postgres did not become ready")

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None,
                 tb: TracebackType | None) -> None:
        subprocess.run(["docker", "rm", "-f", self.name], capture_output=True)

    def fill_tablespace(self) -> int:
        """Append filler until the tablespace refuses to grow; returns filler rows written."""
        rows = 0
        with psycopg.connect(self.url(), autocommit=True) as c:
            c.execute("CREATE TABLE IF NOT EXISTS disk_filler (blob text) TABLESPACE smalldisk")
            while True:
                try:
                    c.execute("INSERT INTO disk_filler SELECT repeat('x', 4000) FROM generate_series(1, 200)")
                    rows += 200
                except psycopg.errors.DiskFull:
                    return rows

    def free_space(self) -> None:
        with psycopg.connect(self.url(), autocommit=True) as c:
            c.execute("DROP TABLE disk_filler")
