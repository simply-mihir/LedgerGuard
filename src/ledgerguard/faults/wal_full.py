"""WAL-volume exhaustion on a throwaway PostgreSQL (the dev databases are never touched).

``pg_wal`` lives on a 48 MB tmpfs and archiving is made to fail, so WAL segments cannot be recycled and
the volume fills. Observed behaviour (asserted by ``tests/test_wal_full.py``): writes fail with SQLSTATE
53100 ("could not write to file pg_wal/..."), which the API classifies as an infrastructure failure
(503, nothing wrapped as a business rejection), and the server then stops, because PostgreSQL cannot
continue without WAL space.

Not covered: restart recovery after WAL exhaustion. That needs a *persistent* size-limited WAL device;
a tmpfs is erased when the container stops, so the post-crash state cannot be examined portably.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from uuid import uuid4

import psycopg

from ledgerguard.db.errors import is_infrastructure_error
from ledgerguard.faults.disk_full import IMAGE

WAL_MB = 48


@dataclass(frozen=True)
class WalFullResult:
    batches_before_failure: int
    error_sqlstate: str | None
    error_is_infrastructure: bool
    server_stopped: bool
    log_mentions_wal: bool


def run_wal_full_drill() -> WalFullResult:
    name = f"lg-walfull-{uuid4().hex[:8]}"
    subprocess.run([
        "docker", "run", "-d", "--name", name, "-e", "POSTGRES_USER=u", "-e", "POSTGRES_PASSWORD=p",
        "-e", "POSTGRES_DB=postgres", "-e", "POSTGRES_INITDB_WALDIR=/walvol/wal",
        "--tmpfs", f"/walvol:rw,size={WAL_MB}m,uid=70,gid=70,mode=0700", "-p", "127.0.0.1::5432",
        IMAGE, "postgres", "-c", "archive_mode=on", "-c", "archive_command=false",
        "-c", "max_wal_size=32MB", "-c", "min_wal_size=32MB", "-c", "wal_keep_size=0",
    ], check=True, capture_output=True)
    try:
        out = subprocess.run(["docker", "port", name, "5432/tcp"], check=True, capture_output=True,
                             text=True).stdout.splitlines()[0]
        url = f"postgresql://u:p@127.0.0.1:{int(out.rsplit(':', 1)[1])}/postgres"
        _wait(url)
        with psycopg.connect(url, autocommit=True) as c:
            c.execute("CREATE TABLE t (i int, p text)")
        batches = 0
        err: Exception | None = None
        try:
            with psycopg.connect(url, autocommit=True) as c:
                while batches < 5000:
                    c.execute("INSERT INTO t SELECT g, repeat('x', 2000) FROM generate_series(1, 500) g")
                    batches += 1
        except Exception as exc:  # noqa: BLE001 - the failure is the subject
            err = exc
        stopped = _wait_stopped(name)
        logs = subprocess.run(["docker", "logs", name], capture_output=True, text=True)
        return WalFullResult(
            batches_before_failure=batches,
            error_sqlstate=getattr(err, "sqlstate", None),
            error_is_infrastructure=bool(err and is_infrastructure_error(err)),
            server_stopped=stopped,
            log_mentions_wal="pg_wal" in (logs.stdout + logs.stderr),
        )
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)


def _wait(url: str, timeout_s: int = 90) -> None:
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        try:
            with psycopg.connect(url, connect_timeout=2):
                pass
            time.sleep(1.5)
            with psycopg.connect(url, connect_timeout=2):
                return
        except psycopg.Error:
            time.sleep(0.5)
    raise RuntimeError("throwaway postgres did not become ready")


def _wait_stopped(name: str, timeout_s: int = 40) -> bool:
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        running = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", name],
                                 capture_output=True, text=True).stdout.strip()
        if running != "true":
            return True
        time.sleep(1)
    return False
