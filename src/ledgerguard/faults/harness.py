"""Environment, process control and invariant checks for real fault-injection scenarios."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID, uuid4

import psycopg
from pydantic import BaseModel

from ledgerguard.audit import verify_journal_chain
from ledgerguard.config import settings
from ledgerguard.conformance import check_trace, fetch_traces
from ledgerguard.coordinator.directory_service import provision_account, register_customer
from ledgerguard.coordinator.reconciliation import run_cross_ledger_reconciliation
from ledgerguard.domain.constants import SYSTEM_CLEARING_ACCOUNT_ID
from ledgerguard.domain.money import AmountPaise
from ledgerguard.faults.proxy import FaultProxy
from ledgerguard.participant.account_service import get_account_balance
from ledgerguard.participant.posting_service import simulate_funding
from ledgerguard.worker.orchestrator import recover_pending_transfers

TERMINAL = ("SETTLED", "CANCELLED", "REJECTED")


class InvariantResult(BaseModel):
    name: str
    passed: bool
    detail: str = ""


def direct_ledger_urls() -> dict[str, str]:
    return {"ledger-1": settings.ledger1_db_url, "ledger-2": settings.ledger2_db_url}


def _hostport(url: str) -> tuple[str, int]:
    p = urlsplit(url)
    return p.hostname or "localhost", p.port or 5432


def via_proxy(url: str, proxy: FaultProxy, connect_timeout_s: int = 3) -> str:
    """Rewrite a database URL to go through ``proxy`` with a bounded connect timeout."""
    p = urlsplit(url)
    creds = f"{p.username}:{p.password}@" if p.username else ""
    query = dict(parse_qsl(p.query))
    query.setdefault("connect_timeout", str(connect_timeout_s))
    return urlunsplit((p.scheme, f"{creds}{proxy.host}:{proxy.port}", p.path, urlencode(query), ""))


def new_account(ledger_id: str, funding: int) -> UUID:
    suffix = uuid4().hex[:10]
    cust = register_customer(settings.coordinator_db_url, "Fault", f"flt-{suffix}@synthetic.local")
    acct = provision_account(
        settings.coordinator_db_url, direct_ledger_urls(), UUID(str(cust["customer_id"])), ledger_id
    )
    acct_id = UUID(str(acct["account_id"]))
    if funding:
        simulate_funding(direct_ledger_urls()[ledger_id], acct_id, AmountPaise(funding))
    return acct_id


@dataclass
class FaultEnv:
    """Fresh accounts, fault proxies and a conservation baseline for one scenario."""

    accounts: dict[UUID, str]
    pairs: list[tuple[UUID, UUID]]
    proxies: dict[str, FaultProxy]
    baseline_funds: int
    baseline_clearing: int

    @classmethod
    def create(cls, pair_count: int = 3, funding: int = 5_000_000) -> FaultEnv:
        accounts: dict[UUID, str] = {}
        pairs: list[tuple[UUID, UUID]] = []
        for _ in range(pair_count):
            s, d = new_account("ledger-1", funding), new_account("ledger-2", 0)
            accounts[s], accounts[d] = "ledger-1", "ledger-2"
            pairs.append((s, d))
        proxies = {
            "coordinator": FaultProxy(_hostport(settings.coordinator_db_url)).start(),
            "ledger-1": FaultProxy(_hostport(settings.ledger1_db_url)).start(),
            "ledger-2": FaultProxy(_hostport(settings.ledger2_db_url)).start(),
        }
        env = cls(accounts, pairs, proxies, 0, 0)
        env.baseline_funds, env.baseline_clearing = env.funds_total(), env.clearing_total()
        return env

    def close(self) -> None:
        for p in self.proxies.values():
            p.stop()

    def heal_all(self) -> None:
        for p in self.proxies.values():
            p.heal()

    # -- observations (always via direct, un-faulted connections) -----------

    def funds_total(self) -> int:
        urls = direct_ledger_urls()
        return sum(get_account_balance(urls[lid], a).posted_balance_minor
                   for a, lid in self.accounts.items())

    def clearing_total(self) -> int:
        return sum(get_account_balance(u, SYSTEM_CLEARING_ACCOUNT_ID).posted_balance_minor
                   for u in direct_ledger_urls().values())

    def transfer_rows(self) -> list[tuple[UUID, str]]:
        with psycopg.connect(settings.coordinator_db_url) as conn:
            return [(r[0], r[1]) for r in conn.execute(
                "SELECT transfer_id, state FROM transfers WHERE source_account_id = ANY(%s)",
                (list(self.accounts),),
            ).fetchall()]

    def transfer_ids(self) -> list[UUID]:
        return [t for t, _ in self.transfer_rows()]


def transfer_state(tid: UUID) -> tuple[str | None, str | None]:
    """(coordinator state, durable decision) for a transfer, or (None, None)."""
    with psycopg.connect(settings.coordinator_db_url) as conn:
        row = conn.execute(
            "SELECT t.state, d.decision FROM transfers t "
            "LEFT JOIN transfer_decisions d USING (transfer_id) WHERE t.transfer_id = %s",
            (tid,),
        ).fetchone()
    return (row[0], row[1]) if row else (None, None)


def recover_until_drained(env: FaultEnv, max_rounds: int = 8) -> int:
    """Run the production recovery loop on direct connections until nothing is in flight."""
    recovered = 0
    for _ in range(max_rounds):
        try:
            pending = [t for t, s in env.transfer_rows() if s not in TERMINAL]
            if not pending:
                return recovered
            recovered += len(recover_pending_transfers(settings.coordinator_db_url,
                                                       direct_ledger_urls()))
        except psycopg.Error:
            # A database that was just crash-restarted can still be shutting down stale
            # backends or replaying WAL; the recovery loop itself must be retryable.
            time.sleep(1.0)
    return recovered


# ---------------------------------------------------------------------------
# Worker subprocess
# ---------------------------------------------------------------------------


class WorkerProcess:
    """A separate OS process performing transfers through the fault proxies."""

    def __init__(self, env: FaultEnv, count: int, pause_ms: int = 0, amount: int = 1_000):
        urls = {
            "coord": via_proxy(settings.coordinator_db_url, env.proxies["coordinator"]),
            "l1": via_proxy(settings.ledger1_db_url, env.proxies["ledger-1"]),
            "l2": via_proxy(settings.ledger2_db_url, env.proxies["ledger-2"]),
        }
        self.events: list[dict[str, object]] = []
        self._lock = threading.Lock()
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "ledgerguard.faults.worker_main",
             "--coord-url", urls["coord"], "--ledger1-url", urls["l1"],
             "--ledger2-url", urls["l2"],
             "--pairs", json.dumps([[str(s), str(d)] for s, d in env.pairs]),
             "--count", str(count), "--amount", str(amount), "--pause-ms", str(pause_ms)],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()

    def _read(self) -> None:
        assert self.proc.stdout is not None
        for line in self.proc.stdout:
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            with self._lock:
                self.events.append(ev)

    def snapshot(self) -> list[dict[str, object]]:
        with self._lock:
            return list(self.events)

    def count(self, event: str) -> int:
        return sum(1 for e in self.snapshot() if e.get("event") == event)

    def started_ids(self) -> list[UUID]:
        return [UUID(str(e["transfer_id"])) for e in self.snapshot() if e.get("event") == "start"]

    def wait_for(self, predicate, timeout_s: float, poll_s: float = 0.005) -> bool:  # type: ignore[no-untyped-def]
        end = time.monotonic() + timeout_s
        while time.monotonic() < end:
            if predicate():
                return True
            if self.proc.poll() is not None and not predicate():
                return False
            time.sleep(poll_s)
        return False

    def kill(self) -> None:
        """SIGKILL: no handlers, no cleanup, exactly like a crashed process."""
        if self.proc.poll() is None:
            self.proc.kill()
        self.proc.wait(timeout=10)
        self._cleanup()

    def _cleanup(self) -> None:
        """Join the reader and close the pipe so no file descriptor leaks."""
        self._reader.join(timeout=5)
        if self.proc.stdout is not None and not self.proc.stdout.closed:
            self.proc.stdout.close()

    def finished(self) -> bool:
        return self.proc.poll() is not None

    def wait(self, timeout_s: float) -> bool:
        try:
            self.proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            return False
        self._cleanup()
        return True


# ---------------------------------------------------------------------------
# Invariants
# ---------------------------------------------------------------------------


def check_invariants(env: FaultEnv, *, expect_drained: bool = True) -> list[InvariantResult]:
    """Evaluate every post-recovery safety invariant using direct connections."""
    out: list[InvariantResult] = []
    rows = env.transfer_rows()
    ids = [t for t, _ in rows]
    states = dict(rows)

    stuck = [str(t) for t, s in rows if s not in TERMINAL]
    out.append(InvariantResult(
        name="all_transfers_terminal", passed=not stuck if expect_drained else True,
        detail=f"{len(rows)} transfers, {len(stuck)} not terminal" + (f": {stuck[:3]}" if stuck else ""),
    ))
    funds = env.funds_total() - env.baseline_funds
    out.append(InvariantResult(name="customer_funds_conserved", passed=funds == 0,
                               detail=f"delta={funds}"))
    clearing = env.clearing_total() - env.baseline_clearing
    out.append(InvariantResult(name="clearing_nets_to_zero", passed=clearing == 0,
                               detail=f"delta={clearing}"))

    urls = direct_ledger_urls()
    active = 0
    for lid, url in urls.items():
        mine = [a for a, led in env.accounts.items() if led == lid]
        with psycopg.connect(url) as conn:
            active += conn.execute(
                "SELECT count(*) FROM holds WHERE account_id = ANY(%s) AND status = 'ACTIVE'",
                (mine,),
            ).fetchone()[0]  # type: ignore[index]
    out.append(InvariantResult(name="no_orphaned_holds", passed=active == 0 if expect_drained else True,
                               detail=f"active holds={active}"))

    counts: dict[tuple[UUID, str], int] = {}
    for url in urls.values():
        with psycopg.connect(url) as conn:
            for tid, op, n in conn.execute(
                "SELECT transfer_id, operation_type, count(*) FROM journal_headers "
                "WHERE transfer_id = ANY(%s) AND operation_type IN ('SOURCE_SETTLE','DESTINATION_SETTLE') "
                "GROUP BY 1, 2", (ids,),
            ).fetchall():
                counts[(tid, op)] = n
    bad: list[str] = []
    for tid, st in rows:
        s_n, d_n = counts.get((tid, "SOURCE_SETTLE"), 0), counts.get((tid, "DESTINATION_SETTLE"), 0)
        if s_n > 1 or d_n > 1:
            bad.append(f"{tid}: duplicate settlement ({s_n},{d_n})")
        elif st == "SETTLED" and (s_n, d_n) != (1, 1):
            bad.append(f"{tid}: SETTLED but journals=({s_n},{d_n})")
        elif st in ("CANCELLED", "REJECTED") and (s_n, d_n) != (0, 0):
            bad.append(f"{tid}: {st} but journals=({s_n},{d_n})")
    out.append(InvariantResult(name="single_settlement_per_transfer", passed=not bad,
                               detail="; ".join(bad[:3]) or f"{len(rows)} transfers checked"))

    with psycopg.connect(settings.coordinator_db_url) as conn:
        decisions: dict[UUID, str] = dict(conn.execute(
            "SELECT transfer_id, decision FROM transfer_decisions WHERE transfer_id = ANY(%s)",
            (ids,),
        ).fetchall())
    flipped = [str(t) for t, d in decisions.items()
               if (d == "COMMIT" and states.get(t) not in ("SETTLED", "COMMITTING"))
               or (d == "CANCEL" and states.get(t) not in ("CANCELLED", "CANCELLING", "REJECTED"))]
    out.append(InvariantResult(name="decision_never_reverted", passed=not flipped,
                               detail=f"{len(decisions)} decisions, {len(flipped)} inconsistent"))

    recon = run_cross_ledger_reconciliation(settings.coordinator_db_url, urls, drained=expect_drained)
    out.append(InvariantResult(name="cross_ledger_reconciliation",
                               passed=recon.status == "PASS" or not expect_drained,
                               detail=f"status={recon.status}"))
    chains = {lid: verify_journal_chain(u, lid).status for lid, u in urls.items()}
    out.append(InvariantResult(name="journal_hash_chains_intact",
                               passed=all(v == "PASS" for v in chains.values()),
                               detail=str(chains)))

    nonconform = [str(t.transfer_id) for t in fetch_traces(settings.coordinator_db_url)
                  if t.transfer_id in set(ids) and not check_trace(list(t.tokens)).accepted]
    out.append(InvariantResult(name="histories_conform_to_tla_spec", passed=not nonconform,
                               detail=f"{len(nonconform)} non-conforming" + (f": {nonconform[:3]}" if nonconform else "")))
    return out


@dataclass
class ScenarioNotes:
    facts: dict[str, object] = field(default_factory=dict)
