"""Silent page corruption, with and without PostgreSQL data checksums.

Two throwaway ``postgres:17-alpine`` containers differ only in ``--data-checksums``. A table is
written, a few bytes inside a tuple are flipped directly in the data file while the server is
stopped, and the table is read back. With checksums the read fails with a checksum error; without
them the server returns the damaged value as if it were correct.

The dev databases are never touched.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from uuid import uuid4

import psycopg

IMAGE = "postgres:17-alpine"
PW = "ledgerguard_admin_secret"
MARK = "LEDGERGUARD" * 10  # 110 bytes of recognisable data inside one tuple


@dataclass
class Outcome:
    checksums_enabled: bool
    read_error: str | None  # SQLSTATE and message when PostgreSQL refused the page
    value_read: str | None  # what a query returned when it did not refuse
    value_written: str = MARK

    @property
    def detected(self) -> bool:
        return self.read_error is not None

    @property
    def silently_wrong(self) -> bool:
        return self.read_error is None and self.value_read != self.value_written


def _sh(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(args), check=check, capture_output=True, text=True)


def _connect(port: int, timeout: float = 60.0) -> psycopg.Connection:
    end = time.monotonic() + timeout
    while True:
        try:
            return psycopg.connect(f"postgresql://postgres:{PW}@127.0.0.1:{port}/postgres",
                                   autocommit=True, connect_timeout=2)
        except psycopg.OperationalError:
            if time.monotonic() > end:
                raise
            time.sleep(0.5)


def _port(name: str) -> int:
    return int(_sh("docker", "port", name, "5432/tcp").stdout.splitlines()[0].rsplit(":", 1)[1])


def corrupt_and_read(checksums: bool) -> Outcome:
    name = f"lg-checksum-{uuid4().hex[:8]}"
    args = ["docker", "run", "-d", "--name", name, "-e", f"POSTGRES_PASSWORD={PW}", "-p", "127.0.0.1::5432"]
    if checksums:
        args += ["-e", "POSTGRES_INITDB_ARGS=--data-checksums"]
    _sh(*args, IMAGE)
    try:
        time.sleep(2.0)  # the image restarts the server once after initialisation
        with _connect(_port(name)) as c:
            enabled = c.execute("SHOW data_checksums").fetchone()[0] == "on"  # type: ignore[index]
            assert enabled == checksums, f"data_checksums={enabled}, expected {checksums}"
            c.execute("CREATE TABLE t (id int, v text)")
            c.execute("INSERT INTO t VALUES (1, %s)", (MARK,))
            c.execute("CHECKPOINT")  # the clean page is now on disk and no buffer is dirty
            rel = c.execute("SELECT pg_relation_filepath('t')").fetchone()[0]  # type: ignore[index]
        # Tuples are packed at the END of the 8 kB page, so 40 bytes before the end is inside the value.
        _sh("docker", "exec", "-u", "postgres", name, "sh", "-c",
            f"printf 'XXXX' | dd of=\"$PGDATA/{rel}\" bs=1 seek=8152 conv=notrunc 2>/dev/null")
        _sh("docker", "restart", "-t", "20", name)  # empties shared buffers; the shutdown writes nothing
        with _connect(_port(name)) as c:
            try:
                row = c.execute("SELECT v FROM t WHERE id = 1").fetchone()
                return Outcome(checksums, None, row[0] if row else None)  # type: ignore[index]
            except psycopg.Error as exc:
                return Outcome(checksums, f"{exc.sqlstate}: {str(exc).splitlines()[0]}", None)
    finally:
        _sh("docker", "rm", "-f", name, check=False)
