"""Three cross-ledger transfer protocols over the *same* accounting kernel.

All three post identical balanced journals through the ``post_journal`` stored
function on independent PostgreSQL ledgers, so differences in the measurements
come from the commit protocol, not from the accounting layer:

* **TCC** - LedgerGuard's production path (holds, durable decision, forward recovery).
* **XA** - PostgreSQL ``PREPARE TRANSACTION`` on both ledgers, then ``COMMIT PREPARED``.
  Row locks are held by the prepared transaction until the coordinator resolves it.
* **Saga** - sequential local commits (debit, then credit) with a compensating
  journal if the second step fails. No isolation between the steps.

The XA and Saga implementations are deliberately minimal baselines. Their
"coordinator log" is in-process state standing in for a durable log; this is a
documented simplification (see docs/protocol_comparison.md).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID, uuid4

import psycopg
from psycopg.types.json import Jsonb

from ledgerguard.config import settings
from ledgerguard.coordinator.failpoints import CrashAfterCommitError, FailpointManager
from ledgerguard.coordinator.transfer_coordinator import submit_coordinator_transfer
from ledgerguard.db.pool import get_connection_pool, get_db_connection
from ledgerguard.domain.constants import SYSTEM_CLEARING_ACCOUNT_ID
from ledgerguard.domain.money import AmountPaise
from ledgerguard.worker.orchestrator import recover_pending_transfers

SETTLED = "SETTLED"
CANCELLED = "CANCELLED"
IN_DOUBT = "IN_DOUBT"  # coordinator crashed; protocol recovery must resolve it
BLOCKED = "BLOCKED"  # the operation could not proceed (lock wait timed out)


class XaUnavailableError(RuntimeError):
    """Raised when the ledgers do not allow prepared transactions."""


@dataclass
class Outcome:
    """Result of a single transfer attempt."""

    state: str
    transfer_id: UUID
    detail: str = ""


class TransferProtocol(Protocol):
    """Common interface exercised by the comparison scenarios."""

    name: str

    def transfer(
        self,
        source: UUID,
        destination: UUID,
        amount: AmountPaise,
        *,
        crash: bool = False,
        lock_timeout_ms: int = 5000,
    ) -> Outcome: ...

    def recover(self) -> int: ...


def _post(
    cur: psycopg.Cursor[Any],
    *,
    transfer_id: UUID,
    operation: str,
    debit: UUID,
    credit: UUID,
    amount: int,
) -> None:
    """Post one balanced two-line journal inside the caller's transaction."""
    lines = [
        {"account_id": str(debit), "side": "DEBIT", "amount_minor": amount},
        {"account_id": str(credit), "side": "CREDIT", "amount_minor": amount},
    ]
    cur.execute(
        "SELECT post_journal(%s, %s, %s, 'INR', %s, %s, %s);",
        (uuid4(), transfer_id, operation, str(transfer_id), operation, Jsonb(lines)),
    )


def _is_lock_timeout(exc: BaseException) -> bool:
    return isinstance(exc, psycopg.errors.LockNotAvailable)


# ---------------------------------------------------------------------------
# TCC (LedgerGuard)
# ---------------------------------------------------------------------------


class TccProtocol:
    """LedgerGuard's Try-Confirm-Cancel workflow with durable decision and recovery."""

    name = "TCC"

    def __init__(self, coord_url: str, ledger_urls: dict[str, str]) -> None:
        self.coord_url = coord_url
        self.ledger_urls = ledger_urls

    def transfer(
        self,
        source: UUID,
        destination: UUID,
        amount: AmountPaise,
        *,
        crash: bool = False,
        lock_timeout_ms: int = 5000,
    ) -> Outcome:
        tid = uuid4()
        fp: FailpointManager | None = None
        if crash:
            fp = FailpointManager()
            fp.set_failpoint("FAIL_AFTER_COMMIT_BEFORE_SOURCE_CONFIRM", tid)
        try:
            res = submit_coordinator_transfer(
                self.coord_url,
                self.ledger_urls,
                idempotency_key=f"cmp-tcc-{tid}",
                source_account_id=source,
                destination_account_id=destination,
                amount=amount,
                transfer_id=tid,
                failpoint_mgr=fp,
            )
        except CrashAfterCommitError:
            return Outcome(IN_DOUBT, tid, "crash after durable COMMIT, before confirms")
        status = str(res.get("status", "UNKNOWN"))
        return Outcome(status, tid, str(res.get("reason", "")))

    def recover(self) -> int:
        return len(recover_pending_transfers(self.coord_url, self.ledger_urls))


# ---------------------------------------------------------------------------
# XA two-phase commit baseline
# ---------------------------------------------------------------------------


@dataclass
class _XaState:
    lock: threading.Lock = field(default_factory=threading.Lock)
    # transfer_id -> (source ledger id, destination ledger id): the TM decision log
    prepared: dict[UUID, tuple[str, str]] = field(default_factory=dict)


class XaProtocol:
    """PostgreSQL ``PREPARE TRANSACTION`` on both ledgers (classic 2PC / XA)."""

    name = "XA-2PC"

    def __init__(self, ledger_urls: dict[str, str], source_ledger: str = "ledger-1",
                 destination_ledger: str = "ledger-2") -> None:
        self.ledger_urls = ledger_urls
        self.src_ledger = source_ledger
        self.dst_ledger = destination_ledger
        self._state = _XaState()
        self.assert_available()

    def assert_available(self) -> None:
        for lid, url in self.ledger_urls.items():
            with psycopg.connect(url) as conn:
                row = conn.execute("SHOW max_prepared_transactions;").fetchone()
            if row is None or int(row[0]) <= 0:
                raise XaUnavailableError(
                    f"{lid}: max_prepared_transactions=0; run `docker compose up -d` to "
                    "recreate ledgers with prepared transactions enabled."
                )

    @staticmethod
    def _gid(transfer_id: UUID, leg: str) -> str:
        return f"lg-cmp-{transfer_id}-{leg}"

    def _prepare_leg(
        self, url: str, tid: UUID, leg: str, operation: str, debit: UUID, credit: UUID,
        amount: int, lock_timeout_ms: int,
    ) -> psycopg.Connection[Any]:
        pool = get_connection_pool(url)
        conn = pool.getconn()
        try:
            xid = conn.xid(0, self._gid(tid, leg), "")
            conn.tpc_begin(xid)
            with conn.cursor() as cur:
                cur.execute(f"SET LOCAL lock_timeout = '{int(lock_timeout_ms)}ms';")
                _post(cur, transfer_id=tid, operation=operation, debit=debit, credit=credit,
                      amount=amount)
            conn.tpc_prepare()
        except BaseException:
            try:
                conn.tpc_rollback()
            except Exception:
                pass
            conn.close()  # never return a connection in an unknown two-phase state
            pool.putconn(conn)
            raise
        return conn

    def _release(self, conn: psycopg.Connection[Any], url: str) -> None:
        get_connection_pool(url).putconn(conn)

    def transfer(
        self,
        source: UUID,
        destination: UUID,
        amount: AmountPaise,
        *,
        crash: bool = False,
        lock_timeout_ms: int = 5000,
    ) -> Outcome:
        tid = uuid4()
        src_url = self.ledger_urls[self.src_ledger]
        dst_url = self.ledger_urls[self.dst_ledger]
        a = amount.paise
        try:
            c1 = self._prepare_leg(src_url, tid, "s", "SOURCE_SETTLE", source,
                                   SYSTEM_CLEARING_ACCOUNT_ID, a, lock_timeout_ms)
        except Exception as exc:
            if _is_lock_timeout(exc):
                return Outcome(BLOCKED, tid, "lock wait timed out on source ledger")
            return Outcome(CANCELLED, tid, f"source prepare failed: {exc}")
        try:
            c2 = self._prepare_leg(dst_url, tid, "d", "DESTINATION_SETTLE",
                                   SYSTEM_CLEARING_ACCOUNT_ID, destination, a, lock_timeout_ms)
        except Exception as exc:
            c1.tpc_rollback()
            self._release(c1, src_url)
            if _is_lock_timeout(exc):
                return Outcome(BLOCKED, tid, "lock wait timed out on destination ledger")
            return Outcome(CANCELLED, tid, f"destination prepare failed: {exc}")

        # Both legs are prepared: row locks are now held by the prepared transactions.
        with self._state.lock:
            self._state.prepared[tid] = (self.src_ledger, self.dst_ledger)
        if crash:
            # The prepared transactions outlive the session; the "process" is gone.
            c1.close()
            c2.close()
            self._release(c1, src_url)
            self._release(c2, dst_url)
            return Outcome(IN_DOUBT, tid, "coordinator crash with both legs prepared")
        c1.tpc_commit()
        c2.tpc_commit()
        self._release(c1, src_url)
        self._release(c2, dst_url)
        with self._state.lock:
            self._state.prepared.pop(tid, None)
        return Outcome(SETTLED, tid)

    def recover(self) -> int:
        """Coordinator restart: drive every prepared pair to COMMIT PREPARED."""
        with self._state.lock:
            pending = dict(self._state.prepared)
        for tid, (sl, dl) in pending.items():
            for lid, leg in ((sl, "s"), (dl, "d")):
                with psycopg.connect(self.ledger_urls[lid]) as conn:
                    conn.tpc_commit(conn.xid(0, self._gid(tid, leg), ""))
            with self._state.lock:
                self._state.prepared.pop(tid, None)
        return len(pending)

    def prepared_count(self) -> int:
        """Number of this protocol's prepared transactions still pinning locks."""
        total = 0
        for url in self.ledger_urls.values():
            with psycopg.connect(url) as conn:
                total += sum(1 for x in conn.tpc_recover() if (x.gtrid or "").startswith("lg-cmp-"))
        return total

    def abort_all_prepared(self) -> int:
        """Test/operations helper: roll back every leftover prepared leg."""
        n = 0
        for url in self.ledger_urls.values():
            with psycopg.connect(url) as conn:
                for x in conn.tpc_recover():
                    if (x.gtrid or "").startswith("lg-cmp-"):
                        conn.tpc_rollback(x)
                        n += 1
        with self._state.lock:
            self._state.prepared.clear()
        return n


# ---------------------------------------------------------------------------
# Saga baseline
# ---------------------------------------------------------------------------


class SagaProtocol:
    """Sequential local commits with a compensating journal on failure."""

    name = "Saga"

    def __init__(self, ledger_urls: dict[str, str], source_ledger: str = "ledger-1",
                 destination_ledger: str = "ledger-2") -> None:
        self.ledger_urls = ledger_urls
        self.src_ledger = source_ledger
        self.dst_ledger = destination_ledger
        self._lock = threading.Lock()
        self._in_flight: dict[UUID, tuple[UUID, UUID, int]] = {}  # the saga log

    def _commit_post(self, url: str, tid: UUID, operation: str, debit: UUID, credit: UUID,
                     amount: int) -> None:
        with get_db_connection(url) as conn:
            with conn.cursor() as cur:
                _post(cur, transfer_id=tid, operation=operation, debit=debit, credit=credit,
                      amount=amount)
            conn.commit()

    def transfer(
        self,
        source: UUID,
        destination: UUID,
        amount: AmountPaise,
        *,
        crash: bool = False,
        lock_timeout_ms: int = 5000,
    ) -> Outcome:
        tid = uuid4()
        a = amount.paise
        src_url = self.ledger_urls[self.src_ledger]
        try:
            self._commit_post(src_url, tid, "SOURCE_SETTLE", source, SYSTEM_CLEARING_ACCOUNT_ID, a)
        except Exception as exc:
            return Outcome(CANCELLED, tid, f"step 1 failed: {exc}")
        with self._lock:
            self._in_flight[tid] = (source, destination, a)
        if crash:
            return Outcome(IN_DOUBT, tid, "crash between saga steps (source already debited)")
        return self._step2(tid, source, destination, a)

    def _step2(self, tid: UUID, source: UUID, destination: UUID, a: int) -> Outcome:
        src_url = self.ledger_urls[self.src_ledger]
        dst_url = self.ledger_urls[self.dst_ledger]
        try:
            self._commit_post(dst_url, tid, "DESTINATION_SETTLE", SYSTEM_CLEARING_ACCOUNT_ID,
                              destination, a)
        except Exception as exc:
            # Compensating journal: a new entry, never an edit of history.
            self._commit_post(src_url, tid, "REVERSAL", SYSTEM_CLEARING_ACCOUNT_ID, source, a)
            with self._lock:
                self._in_flight.pop(tid, None)
            return Outcome(CANCELLED, tid, f"step 2 failed, compensated: {exc}")
        with self._lock:
            self._in_flight.pop(tid, None)
        return Outcome(SETTLED, tid)

    def recover(self) -> int:
        with self._lock:
            pending = dict(self._in_flight)
        for tid, (s, d, a) in pending.items():
            self._step2(tid, s, d, a)
        return len(pending)


def all_protocols(
    coord_url: str | None = None, ledger_urls: dict[str, str] | None = None
) -> list[TransferProtocol]:
    """Build the three protocols against the configured databases."""
    coord = coord_url or settings.coordinator_db_url
    urls = ledger_urls or {"ledger-1": settings.ledger1_db_url, "ledger-2": settings.ledger2_db_url}
    return [TccProtocol(coord, urls), XaProtocol(urls), SagaProtocol(urls)]
