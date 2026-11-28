"""Deterministic isolation-level study on PostgreSQL.

Two (or more) real sessions are interleaved step by step, so each anomaly is reproduced the same
way every run rather than hoped for under load. The textbook anomalies run against a throwaway
schema (dropped afterwards); the final scenario drives the real ``post_journal`` function.

Every cell reports one of:

* ``ANOMALY``          - the interleaving committed and the invariant is violated afterwards.
* ``ABORTED_RETRY_OK`` - PostgreSQL aborted a session with SQLSTATE 40001; re-running that whole
                         transaction restored the invariant. This is the "retry" contract.
* ``SAFE``             - no abort was needed and the invariant holds.

Money is integer minor units throughout. Nothing here touches posted journal history except the
real-system scenario, which only appends new journals through ``post_journal``.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg import IsolationLevel

from ledgerguard.config import settings
from ledgerguard.db.retry import run_with_transient_retry
from ledgerguard.domain.constants import SYSTEM_CASH_ACCOUNT_ID
from ledgerguard.domain.money import AmountPaise
from ledgerguard.participant.account_service import create_ledger_account
from ledgerguard.participant.posting_service import simulate_funding

LEVELS: tuple[IsolationLevel, ...] = (
    IsolationLevel.READ_COMMITTED,
    IsolationLevel.REPEATABLE_READ,
    IsolationLevel.SERIALIZABLE,
)
LEVEL_NAMES = {
    IsolationLevel.READ_COMMITTED: "READ COMMITTED",
    IsolationLevel.REPEATABLE_READ: "REPEATABLE READ",
    IsolationLevel.SERIALIZABLE: "SERIALIZABLE",
}
ANOMALY = "ANOMALY"
ABORTED_RETRY_OK = "ABORTED_RETRY_OK"
SAFE = "SAFE"


@dataclass
class Cell:
    scenario: str
    mitigation: str
    level: str
    outcome: str
    detail: dict[str, Any] = field(default_factory=dict)


class _Session:
    """One database session with an explicit isolation level."""

    def __init__(self, url: str, schema: str, level: IsolationLevel) -> None:
        self.conn = psycopg.connect(url, autocommit=False)
        self.conn.isolation_level = level
        self.conn.execute(f"SET search_path = {schema}")
        self.conn.commit()
        row = self.conn.execute("SELECT pg_backend_pid()").fetchone()
        assert row is not None
        self.pid: int = row[0]

    def q(self, sql: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
        cur = self.conn.execute(sql, params)
        return cur.fetchall() if cur.description else []

    def one(self, sql: str, params: tuple[Any, ...] = ()) -> Any:
        return self.q(sql, params)[0][0]

    def commit(self) -> None:
        self.conn.commit()

    def rollback(self) -> None:
        self.conn.rollback()

    def close(self) -> None:
        self.conn.close()


class _Blocked:
    """Run a callable on another thread and report whether it is waiting on a lock."""

    def __init__(self, fn: Callable[[], Any]) -> None:
        self.result: Any = None
        self.error: BaseException | None = None
        self._thread = threading.Thread(target=self._run, args=(fn,), daemon=True)
        self._thread.start()

    def _run(self, fn: Callable[[], Any]) -> None:
        try:
            self.result = fn()
        except BaseException as exc:  # noqa: BLE001 - surfaced to the caller on join
            self.error = exc

    def join(self, timeout: float = 20.0) -> None:
        self._thread.join(timeout)
        if self._thread.is_alive():
            raise TimeoutError("blocked session never finished")


def _wait_until_blocked(admin_url: str, pid: int, timeout: float = 10.0) -> None:
    """Block until backend ``pid`` is waiting on a heavyweight lock (deterministic ordering)."""
    deadline = time.monotonic() + timeout
    with psycopg.connect(admin_url, autocommit=True) as probe:
        while time.monotonic() < deadline:
            row = probe.execute(
                "SELECT wait_event_type FROM pg_stat_activity WHERE pid = %s", (pid,)
            ).fetchone()
            if row and row[0] == "Lock":
                return
            time.sleep(0.01)
    raise TimeoutError(f"backend {pid} never blocked on a lock")


def _is_serialization_failure(exc: BaseException | None) -> bool:
    return isinstance(exc, psycopg.errors.SerializationFailure)


class _Scratch:
    """A throwaway schema holding the study tables."""

    def __init__(self, admin_url: str) -> None:
        self.admin_url = admin_url
        self.schema = f"isolation_study_{uuid4().hex[:10]}"

    def __enter__(self) -> _Scratch:
        with psycopg.connect(self.admin_url, autocommit=True) as c:
            c.execute(f"CREATE SCHEMA {self.schema}")
            c.execute(
                f"CREATE TABLE {self.schema}.acct (id TEXT PRIMARY KEY, bal BIGINT NOT NULL)"
            )
            c.execute(
                f"CREATE TABLE {self.schema}.item (id SERIAL PRIMARY KEY, amount BIGINT NOT NULL)"
            )
        return self

    def reset(self, rows: dict[str, int], items: tuple[int, ...] = ()) -> None:
        with psycopg.connect(self.admin_url, autocommit=True) as c:
            c.execute(f"TRUNCATE {self.schema}.acct, {self.schema}.item RESTART IDENTITY")
            for k, v in rows.items():
                c.execute(f"INSERT INTO {self.schema}.acct VALUES (%s, %s)", (k, v))
            for a in items:
                c.execute(f"INSERT INTO {self.schema}.item (amount) VALUES (%s)", (a,))

    def read(self) -> dict[str, int]:
        with psycopg.connect(self.admin_url, autocommit=True) as c:
            rows = c.execute(f"SELECT id, bal FROM {self.schema}.acct ORDER BY id").fetchall()
        return {r[0]: r[1] for r in rows}

    def session(self, level: IsolationLevel) -> _Session:
        return _Session(self.admin_url, self.schema, level)

    def __exit__(self, *exc: object) -> None:
        with psycopg.connect(self.admin_url, autocommit=True) as c:
            c.execute(f"DROP SCHEMA IF EXISTS {self.schema} CASCADE")


# --------------------------------------------------------------------------------------------
# Lost update: two withdrawals (30 and 50) from a balance of 100. Correct final balance: 20.
# --------------------------------------------------------------------------------------------


def lost_update(scratch: _Scratch, level: IsolationLevel, mitigation: str) -> Cell:
    scratch.reset({"a": 100})
    s1, s2 = scratch.session(level), scratch.session(level)
    aborted = False
    try:
        if mitigation == "none":
            # Read-modify-write in the application: both read 100 before either writes.
            b1 = s1.one("SELECT bal FROM acct WHERE id = 'a'")
            b2 = s2.one("SELECT bal FROM acct WHERE id = 'a'")
            s1.q("UPDATE acct SET bal = %s WHERE id = 'a'", (b1 - 30,))
            s1.commit()
            try:
                s2.q("UPDATE acct SET bal = %s WHERE id = 'a'", (b2 - 50,))
                s2.commit()
            except psycopg.Error as exc:
                if not _is_serialization_failure(exc):
                    raise
                s2.rollback()
                aborted = True
        elif mitigation in ("select_for_update", "atomic_update"):
            if mitigation == "select_for_update":
                b1 = s1.one("SELECT bal FROM acct WHERE id = 'a' FOR UPDATE")
                s1.q("UPDATE acct SET bal = %s WHERE id = 'a'", (b1 - 30,))
            else:
                s1.q("UPDATE acct SET bal = bal - 30 WHERE id = 'a'")

            def second() -> None:
                if mitigation == "select_for_update":
                    b2 = s2.one("SELECT bal FROM acct WHERE id = 'a' FOR UPDATE")
                    s2.q("UPDATE acct SET bal = %s WHERE id = 'a'", (b2 - 50,))
                else:
                    s2.q("UPDATE acct SET bal = bal - 50 WHERE id = 'a'")
                s2.commit()

            waiter = _Blocked(second)
            _wait_until_blocked(scratch.admin_url, s2.pid)  # s2 really is queued behind s1
            s1.commit()
            waiter.join()
            if waiter.error is not None:
                if not _is_serialization_failure(waiter.error):
                    raise waiter.error
                s2.rollback()
                aborted = True
        else:
            raise ValueError(mitigation)
    finally:
        s1.close()
        s2.close()

    if aborted:  # the retry contract: re-run the whole aborted transaction in a fresh session
        s3 = scratch.session(level)
        try:
            s3.q("UPDATE acct SET bal = bal - 50 WHERE id = 'a'")
            s3.commit()
        finally:
            s3.close()
    final = scratch.read()["a"]
    outcome = ANOMALY if final != 20 else (ABORTED_RETRY_OK if aborted else SAFE)
    return Cell("lost_update", mitigation, LEVEL_NAMES[level], outcome,
                {"final_balance_minor": final, "expected_minor": 20})


# --------------------------------------------------------------------------------------------
# Write skew: joint rule a + b >= 0. Each session withdraws 80 from its own row after reading
# a + b = 100. They write *different rows*, so there is no write-write conflict to detect.
# --------------------------------------------------------------------------------------------


def write_skew(scratch: _Scratch, level: IsolationLevel, mitigation: str) -> Cell:
    scratch.reset({"a": 50, "b": 50})
    s1, s2 = scratch.session(level), scratch.session(level)
    aborted = False
    read_sql = "SELECT COALESCE(SUM(bal), 0) FROM acct"
    if mitigation == "lock_both_rows":
        read_sql = "SELECT COALESCE(SUM(bal), 0) FROM (SELECT bal FROM acct FOR UPDATE) x"

    def withdraw(s: _Session, row: str) -> bool:
        """The business rule. Returns False when it refuses (joint balance too low)."""
        total = s.one(read_sql)
        if total - 80 < 0:
            s.rollback()
            return False
        s.q("UPDATE acct SET bal = bal - 80 WHERE id = %s", (row,))
        s.commit()
        return True

    try:
        if mitigation == "none":
            # Both sessions read the sum before either writes (snapshots taken, then both act).
            t1 = s1.one(read_sql)
            t2 = s2.one(read_sql)
            assert t1 == 100 and t2 == 100
            s1.q("UPDATE acct SET bal = bal - 80 WHERE id = 'a'")
            s1.commit()
            try:
                s2.q("UPDATE acct SET bal = bal - 80 WHERE id = 'b'")
                s2.commit()
            except psycopg.Error as exc:
                if not _is_serialization_failure(exc):
                    raise
                s2.rollback()
                aborted = True
        elif mitigation == "lock_both_rows":
            t1 = s1.one(read_sql)
            assert t1 == 100
            s1.q("UPDATE acct SET bal = bal - 80 WHERE id = 'a'")

            def second() -> bool:
                return withdraw(s2, "b")

            waiter = _Blocked(second)
            _wait_until_blocked(scratch.admin_url, s2.pid)
            s1.commit()
            waiter.join()
            if waiter.error is not None:
                if not _is_serialization_failure(waiter.error):
                    raise waiter.error
                s2.rollback()
                aborted = True
        else:
            raise ValueError(mitigation)
    finally:
        s1.close()
        s2.close()

    if aborted:  # retry the aborted withdrawal from scratch: it must now see a + b = 20 and refuse
        s3 = scratch.session(level)
        try:
            withdraw(s3, "b")
        finally:
            s3.close()
    final = scratch.read()
    total = sum(final.values())
    outcome = ANOMALY if total < 0 else (ABORTED_RETRY_OK if aborted else SAFE)
    return Cell("write_skew", mitigation, LEVEL_NAMES[level], outcome,
                {"final_balances_minor": final, "joint_total_minor": total, "rule": "a + b >= 0"})


# --------------------------------------------------------------------------------------------
# Non-repeatable read and phantom read.
# --------------------------------------------------------------------------------------------


def non_repeatable_read(scratch: _Scratch, level: IsolationLevel, mitigation: str = "none") -> Cell:
    scratch.reset({"a": 100})
    s1, s2 = scratch.session(level), scratch.session(IsolationLevel.READ_COMMITTED)
    try:
        first = s1.one("SELECT bal FROM acct WHERE id = 'a'")
        s2.q("UPDATE acct SET bal = 70 WHERE id = 'a'")
        s2.commit()
        second = s1.one("SELECT bal FROM acct WHERE id = 'a'")
        s1.commit()
    finally:
        s1.close()
        s2.close()
    return Cell("non_repeatable_read", mitigation, LEVEL_NAMES[level],
                ANOMALY if first != second else SAFE, {"first_read": first, "second_read": second})


def phantom_read(scratch: _Scratch, level: IsolationLevel, mitigation: str = "none") -> Cell:
    scratch.reset({}, items=(100, 200))
    s1, s2 = scratch.session(level), scratch.session(IsolationLevel.READ_COMMITTED)
    try:
        first = s1.one("SELECT count(*) FROM item WHERE amount >= 100")
        s2.q("INSERT INTO item (amount) VALUES (300)")
        s2.commit()
        second = s1.one("SELECT count(*) FROM item WHERE amount >= 100")
        s1.commit()
    finally:
        s1.close()
        s2.close()
    return Cell("phantom_read", mitigation, LEVEL_NAMES[level],
                ANOMALY if first != second else SAFE, {"first_count": first, "second_count": second})


# --------------------------------------------------------------------------------------------
# The real post_journal under concurrent overdraft attempts at each isolation level.
# --------------------------------------------------------------------------------------------


@dataclass
class RealPostingResult:
    level: str
    workers: int
    funded_minor: int
    amount_minor: int
    succeeded: int
    rejected_insufficient: int
    retries: int
    final_balance_minor: int
    expected_succeeded: int
    invariant_holds: bool
    seconds: float


def _post_cash_out(db_url: str, level: IsolationLevel, account_id: UUID, amount: int) -> None:
    """One complete local transaction: debit the customer wallet, credit platform cash."""
    import json

    lines = [
        {"account_id": str(account_id), "side": "DEBIT", "amount_minor": amount},
        {"account_id": str(SYSTEM_CASH_ACCOUNT_ID), "side": "CREDIT", "amount_minor": amount},
    ]
    with psycopg.connect(db_url, autocommit=False) as conn:
        conn.isolation_level = level
        try:
            conn.execute(
                "SELECT post_journal(%s, NULL, 'CASH_OUT', 'INR', NULL, 'isolation study', %s::jsonb)",
                (uuid4(), json.dumps(lines)),
            )
            conn.commit()
        except BaseException:
            conn.rollback()
            raise


def real_posting(level: IsolationLevel, workers: int = 8, funded_for: int = 3,
                 amount: int = 1_000) -> RealPostingResult:
    """``workers`` concurrent debits against a wallet funded for only ``funded_for`` of them.

    Safety demands exactly ``funded_for`` succeed, the rest are rejected for insufficient funds,
    and the balance never goes negative - at every isolation level, with the standard retry on
    40001/40P01 applied around each whole transaction.
    """
    db_url = settings.ledger1_db_url
    account = create_ledger_account(db_url).account_id
    funded = funded_for * amount
    simulate_funding(db_url, account, AmountPaise(funded))

    barrier = threading.Barrier(workers)
    lock = threading.Lock()
    tally = {"ok": 0, "rejected": 0, "attempts": 0, "unexpected": 0}
    errors: list[BaseException] = []

    def worker() -> None:
        def attempt() -> None:
            with lock:
                tally["attempts"] += 1
            _post_cash_out(db_url, level, account, amount)

        barrier.wait()
        try:
            run_with_transient_retry(attempt, operation_name="isolation_study.cash_out",
                                     max_retries=50, base_delay_ms=1.0, max_delay_ms=20.0)
            with lock:
                tally["ok"] += 1
        except psycopg.errors.CheckViolation:
            with lock:
                tally["rejected"] += 1
        except BaseException as exc:  # noqa: BLE001 - recorded, never swallowed
            with lock:
                tally["unexpected"] += 1
                errors.append(exc)

    started = time.monotonic()
    threads = [threading.Thread(target=worker) for _ in range(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(120)
    seconds = time.monotonic() - started
    if errors:
        raise errors[0]

    with psycopg.connect(db_url) as conn:
        row = conn.execute(
            "SELECT posted_balance_minor FROM account_balances WHERE account_id = %s", (account,)
        ).fetchone()
    assert row is not None
    final = int(row[0])
    holds = (
        tally["ok"] == funded_for
        and tally["rejected"] == workers - funded_for
        and final == funded - tally["ok"] * amount
        and final >= 0
    )
    return RealPostingResult(
        level=LEVEL_NAMES[level], workers=workers, funded_minor=funded, amount_minor=amount,
        succeeded=tally["ok"], rejected_insufficient=tally["rejected"],
        retries=tally["attempts"] - workers, final_balance_minor=final,
        expected_succeeded=funded_for, invariant_holds=holds, seconds=round(seconds, 3),
    )


# --------------------------------------------------------------------------------------------


@dataclass
class IsolationReport:
    cells: list[Cell]
    real: list[RealPostingResult]
    server_version: str

    def matrix(self) -> dict[tuple[str, str], dict[str, str]]:
        out: dict[tuple[str, str], dict[str, str]] = {}
        for c in self.cells:
            out.setdefault((c.scenario, c.mitigation), {})[c.level] = c.outcome
        return out


_SCENARIOS: tuple[tuple[Callable[..., Cell], tuple[str, ...]], ...] = (
    (lost_update, ("none", "select_for_update", "atomic_update")),
    (write_skew, ("none", "lock_both_rows")),
    (non_repeatable_read, ("none",)),
    (phantom_read, ("none",)),
)


def run_isolation_study(real_workers: int = 8) -> IsolationReport:
    cells: list[Cell] = []
    with _Scratch(settings.ledger1_admin_db_url) as scratch:
        for fn, mitigations in _SCENARIOS:
            for mitigation in mitigations:
                for level in LEVELS:
                    cells.append(fn(scratch, level, mitigation))
    real = [real_posting(level, workers=real_workers) for level in LEVELS]
    with psycopg.connect(settings.ledger1_db_url) as conn:
        row = conn.execute("SHOW server_version").fetchone()
    return IsolationReport(cells=cells, real=real, server_version=str(row[0]) if row else "?")


def report_markdown(report: IsolationReport) -> str:
    lines = [
        "# Isolation-level study",
        "",
        f"PostgreSQL {report.server_version}. Every cell is a deterministic two-session "
        "interleaving (no timing luck).",
        "",
        "`ANOMALY` = invariant violated after both commits; `ABORTED_RETRY_OK` = PostgreSQL "
        "raised 40001 and re-running the aborted transaction restored the invariant; "
        "`SAFE` = no abort needed.",
        "",
        "| Scenario | Mitigation | READ COMMITTED | REPEATABLE READ | SERIALIZABLE |",
        "|---|---|---|---|---|",
    ]
    for (scenario, mitigation), row in report.matrix().items():
        lines.append(
            f"| {scenario} | {mitigation} | {row['READ COMMITTED']} | "
            f"{row['REPEATABLE READ']} | {row['SERIALIZABLE']} |"
        )
    lines += [
        "",
        "## Real `post_journal` under concurrent overdraft",
        "",
        "Concurrent cash-outs against a wallet funded for only some of them, each a whole "
        "transaction wrapped in the standard 40001/40P01 retry.",
        "",
        "| Level | Workers | Funded for | Succeeded | Rejected (insufficient) | Retries | "
        "Final balance | Invariant |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in report.real:
        lines.append(
            f"| {r.level} | {r.workers} | {r.expected_succeeded} | {r.succeeded} | "
            f"{r.rejected_insufficient} | {r.retries} | {r.final_balance_minor} | "
            f"{'holds' if r.invariant_holds else 'VIOLATED'} |"
        )
    return "\n".join(lines) + "\n"


__all__ = [
    "ABORTED_RETRY_OK", "ANOMALY", "Cell", "IsolationReport", "LEVELS", "RealPostingResult",
    "SAFE", "lost_update", "non_repeatable_read", "phantom_read", "real_posting",
    "report_markdown", "run_isolation_study", "write_skew",
]
