"""Measured scenarios comparing TCC, XA 2PC and Saga on real PostgreSQL ledgers."""

from __future__ import annotations

import json
import math
import os
import platform
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import UUID, uuid4

import psycopg
from pydantic import BaseModel, Field

from ledgerguard.comparison.protocols import (
    CANCELLED,
    IN_DOUBT,
    SETTLED,
    SagaProtocol,
    TccProtocol,
    TransferProtocol,
    XaProtocol,
)
from ledgerguard.comparison.stats import distinguishable, summarize
from ledgerguard.config import settings
from ledgerguard.coordinator.directory_service import provision_account, register_customer
from ledgerguard.domain.constants import SYSTEM_CLEARING_ACCOUNT_ID
from ledgerguard.domain.models import AccountStatus
from ledgerguard.domain.money import AmountPaise
from ledgerguard.evidence import collect as collect_provenance
from ledgerguard.participant.account_service import get_account_balance, set_account_status
from ledgerguard.participant.posting_service import simulate_funding


class ComparisonConfig(BaseModel):
    """Parameters of one comparison run."""

    ops: int = 24
    repeats: int = 1  # independent measured runs per (protocol, workload); >1 adds CIs
    warmup_ops: int = 8  # discarded warm-up run before measuring (only when repeats > 1)
    workers: int = 4
    amount_minor: int = 1_000
    funding_minor: int = 5_000_000
    bystander_timeout_ms: int = 1_500
    protocols: list[str] = Field(default_factory=lambda: ["TCC", "XA-2PC", "Saga"])


class ThroughputResult(BaseModel):
    protocol: str
    workload: str
    ops: int
    workers: int
    settled: int
    not_settled: int
    seconds: float
    tps: float
    p50_ms: float
    p95_ms: float
    repeats: int = 1
    tps_sd: float = 0.0
    tps_ci95: tuple[float, float] | None = None
    p50_ci95: tuple[float, float] | None = None
    p95_ci95: tuple[float, float] | None = None
    tps_runs: list[float] = Field(default_factory=list)


class CrashResult(BaseModel):
    """Coordinator crash at the protocol's most vulnerable point."""

    protocol: str
    crash_point: str
    outcome_at_crash: str
    customer_funds_delta_in_window: int
    partial_posting_visible: bool
    resources_pinned_in_window: str
    bystander_state: str
    bystander_wait_ms: float
    recovery_ms: float
    customer_funds_delta_after: int
    clearing_delta_after: int
    unresolved_after: int


class FailureResult(BaseModel):
    """Destination participant rejects the transfer (closed account)."""

    protocol: str
    final_state: str
    customer_funds_delta: int
    clearing_delta: int
    journals_written: int
    atomic: bool


class ComparisonReport(BaseModel):
    schema_version: int = 1
    generated_at: str
    git_sha: str
    git_tree: str = "unknown"
    working_tree_clean: bool = False
    environment: dict[str, str]
    config: ComparisonConfig
    throughput: list[ThroughputResult]
    crash: list[CrashResult]
    failure: list[FailureResult]

    def to_markdown(self) -> str:
        lines = [
            "# Protocol comparison: TCC vs XA 2PC vs Saga",
            "",
            f"- Generated: `{self.generated_at}` at commit `{self.git_sha}` (tree `{self.git_tree}`, clean={self.working_tree_clean})",
            f"- Environment: {self.environment}",
            f"- Config: ops={self.config.ops}, workers={self.config.workers}, "
            f"amount={self.config.amount_minor} paise",
            "",
            "## S1. Throughput and latency (settled transfers only)",
            "",
            f"Each cell is the mean over `repeats` independent runs (protocols interleaved "
            f"round-robin, one discarded warm-up run); brackets are 95% Student-t confidence "
            f"intervals across runs. `ops` per run = {self.config.ops}.",
            "",
            "| Protocol | Workload | Runs | Settled/Ops (last run) | TPS mean [95% CI] | TPS sd | "
            "P50 ms mean [95% CI] | P95 ms mean [95% CI] |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]

        def ci(mean: float, bounds: tuple[float, float] | None) -> str:
            if bounds is None or not all(map(math.isfinite, bounds)):
                return f"{mean}"
            return f"{mean} [{bounds[0]:.2f}, {bounds[1]:.2f}]"

        for t in self.throughput:
            lines.append(
                f"| {t.protocol} | {t.workload} | {t.repeats} | {t.settled}/{t.ops} | "
                f"{ci(t.tps, t.tps_ci95)} | {t.tps_sd} | {ci(t.p50_ms, t.p50_ci95)} | "
                f"{ci(t.p95_ms, t.p95_ci95)} |"
            )
        lines += ["", "TPS differences between protocols (non-overlapping 95% CIs):", ""]
        for workload in ("uncontended", "hot_source"):
            rows = [t for t in self.throughput if t.workload == workload and t.tps_ci95]
            for i, a in enumerate(rows):
                for b in rows[i + 1 :]:
                    assert a.tps_ci95 and b.tps_ci95
                    verdict = ("distinguishable" if distinguishable(a.tps_ci95, b.tps_ci95)
                               else "NOT distinguishable")
                    lines.append(f"- {workload}: {a.protocol} vs {b.protocol}: {verdict}")
        lines += [
            "",
            "## S2. Coordinator crash mid-transfer",
            "",
            "| Protocol | Crash point | Partial posting visible | Pinned in window | "
            "Bystander | Bystander wait ms | Recovery ms | Funds delta after | "
            "Clearing delta after | Unresolved after |",
            "|---|---|---|---|---|---:|---:|---:|---:|---:|",
        ]
        for c in self.crash:
            lines.append(
                f"| {c.protocol} | {c.crash_point} | {c.partial_posting_visible} | "
                f"{c.resources_pinned_in_window} | {c.bystander_state} | "
                f"{c.bystander_wait_ms} | {c.recovery_ms} | {c.customer_funds_delta_after} | "
                f"{c.clearing_delta_after} | {c.unresolved_after} |"
            )
        lines += [
            "",
            "## S3. Destination rejects the transfer",
            "",
            "| Protocol | Final state | Atomic | Customer funds delta | Clearing delta | "
            "Journals written |",
            "|---|---|---|---:|---:|---:|",
        ]
        for f in self.failure:
            lines.append(
                f"| {f.protocol} | {f.final_state} | {f.atomic} | {f.customer_funds_delta} | "
                f"{f.clearing_delta} | {f.journals_written} |"
            )
        return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Fixtures and probes
# ---------------------------------------------------------------------------


def _urls() -> dict[str, str]:
    return {"ledger-1": settings.ledger1_db_url, "ledger-2": settings.ledger2_db_url}


def _new_account(ledger_id: str, funding: int) -> UUID:
    suffix = uuid4().hex[:10]
    cust = register_customer(
        settings.coordinator_db_url, "Comparison", f"cmp-{suffix}@synthetic.local"
    )
    acct = provision_account(
        settings.coordinator_db_url, _urls(), UUID(str(cust["customer_id"])), ledger_id
    )
    acct_id = UUID(str(acct["account_id"]))
    if funding > 0:
        simulate_funding(_urls()[ledger_id], acct_id, AmountPaise(funding))
    return acct_id


def _ledger_of(account: UUID, accounts: dict[UUID, str]) -> str:
    return accounts[account]


def _customer_total(accounts: dict[UUID, str]) -> int:
    urls = _urls()
    return sum(
        get_account_balance(urls[lid], acct).posted_balance_minor for acct, lid in accounts.items()
    )


def _held_total(accounts: dict[UUID, str]) -> int:
    urls = _urls()
    return sum(
        get_account_balance(urls[lid], acct).held_amount_minor for acct, lid in accounts.items()
    )


def _clearing_total() -> int:
    urls = _urls()
    return sum(
        get_account_balance(url, SYSTEM_CLEARING_ACCOUNT_ID).posted_balance_minor
        for url in urls.values()
    )


def _journal_count() -> int:
    total = 0
    for url in _urls().values():
        with psycopg.connect(url) as conn:
            row = conn.execute("SELECT count(*) FROM journal_headers;").fetchone()
        total += int(row[0]) if row else 0
    return total


def _unresolved(proto: TransferProtocol) -> int:
    if isinstance(proto, XaProtocol):
        return proto.prepared_count()
    if isinstance(proto, SagaProtocol):
        with proto._lock:
            return len(proto._in_flight)
    with psycopg.connect(settings.coordinator_db_url) as conn:
        row = conn.execute(
            "SELECT count(*) FROM transfers WHERE state NOT IN ('SETTLED', 'CANCELLED') "
            "AND idempotency_key LIKE 'cmp-tcc-%';"
        ).fetchone() if _has_idem_col() else None
    return int(row[0]) if row else 0


def _has_idem_col() -> bool:
    with psycopg.connect(settings.coordinator_db_url) as conn:
        row = conn.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name='transfers' AND column_name='idempotency_key';"
        ).fetchone()
    return row is not None


def _pinned(proto: TransferProtocol, accounts: dict[UUID, str]) -> str:
    if isinstance(proto, XaProtocol):
        return f"{proto.prepared_count()} prepared txns holding row locks on both ledgers"
    if isinstance(proto, SagaProtocol):
        return "none (source already debited and committed)"
    return f"{_held_total(accounts)} paise held as rows (no row locks held)"


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


def _pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, int(round(q * (len(ordered) - 1))))
    return round(ordered[idx], 2)


def _throughput_once(proto: TransferProtocol, workload: str, cfg: ComparisonConfig,
                     ops: int) -> ThroughputResult:
    if workload == "uncontended":
        pairs = [
            (_new_account("ledger-1", cfg.funding_minor), _new_account("ledger-2", 0))
            for _ in range(cfg.workers)
        ]
    else:  # hot_source: every worker debits the same account
        hot = _new_account("ledger-1", cfg.funding_minor)
        pairs = [(hot, _new_account("ledger-2", 0)) for _ in range(cfg.workers)]

    amount = AmountPaise(cfg.amount_minor)
    latencies: list[float] = []
    states: list[str] = []

    def one(i: int) -> None:
        src, dst = pairs[i % len(pairs)]
        t0 = time.perf_counter()
        out = proto.transfer(src, dst, amount, lock_timeout_ms=10_000)
        latencies.append((time.perf_counter() - t0) * 1000)
        states.append(out.state)

    t_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=cfg.workers) as pool:
        list(pool.map(one, range(ops)))
    elapsed = time.perf_counter() - t_start
    settled = states.count(SETTLED)
    return ThroughputResult(
        protocol=proto.name,
        workload=workload,
        ops=ops,
        workers=cfg.workers,
        settled=settled,
        not_settled=len(states) - settled,
        seconds=round(elapsed, 3),
        tps=round(settled / elapsed, 2) if elapsed > 0 else 0.0,
        p50_ms=_pct(latencies, 0.5),
        p95_ms=_pct(latencies, 0.95),
    )


def _throughput_all(protos: list[TransferProtocol], cfg: ComparisonConfig) -> list[ThroughputResult]:
    """Measure every (protocol, workload) ``cfg.repeats`` times, interleaved round-robin so
    slow drift (thermal throttling, cache warm-up, background load) hits all protocols alike."""
    cells = [(p, w) for p in protos for w in ("uncontended", "hot_source")]
    if cfg.repeats > 1 and cfg.warmup_ops > 0:
        for p, w in cells:
            _throughput_once(p, w, cfg, cfg.warmup_ops)  # discarded
    runs: dict[tuple[str, str], list[ThroughputResult]] = {(p.name, w): [] for p, w in cells}
    for _ in range(max(1, cfg.repeats)):
        for p, w in cells:
            runs[(p.name, w)].append(_throughput_once(p, w, cfg, cfg.ops))
    out: list[ThroughputResult] = []
    for p, w in cells:
        rs = runs[(p.name, w)]
        tps_m, tps_sd, tps_lo, tps_hi = summarize([r.tps for r in rs])
        p50_m, _, p50_lo, p50_hi = summarize([r.p50_ms for r in rs])
        p95_m, _, p95_lo, p95_hi = summarize([r.p95_ms for r in rs])
        last = rs[-1]
        many = len(rs) > 1
        out.append(last.model_copy(update={
            "tps": round(tps_m, 2), "p50_ms": round(p50_m, 2), "p95_ms": round(p95_m, 2),
            "repeats": len(rs), "tps_sd": round(tps_sd, 2),
            "settled": min(r.settled for r in rs), "not_settled": max(r.not_settled for r in rs),
            "tps_ci95": (tps_lo, tps_hi) if many else None,
            "p50_ci95": (p50_lo, p50_hi) if many else None,
            "p95_ci95": (p95_lo, p95_hi) if many else None,
            "tps_runs": [r.tps for r in rs],
        }))
    return out


_CRASH_POINT = {
    "TCC": "after durable COMMIT decision, before confirms",
    "XA-2PC": "both legs PREPARED, before COMMIT PREPARED",
    "Saga": "after step 1 (source debited), before step 2",
}


def _crash(proto: TransferProtocol, cfg: ComparisonConfig) -> CrashResult:
    src = _new_account("ledger-1", cfg.funding_minor)
    dst = _new_account("ledger-2", 0)
    dst_bystander = _new_account("ledger-2", 0)
    accounts = {src: "ledger-1", dst: "ledger-2", dst_bystander: "ledger-2"}
    funds0 = _customer_total(accounts)
    clearing0 = _clearing_total()

    out = proto.transfer(src, dst, AmountPaise(cfg.amount_minor), crash=True)
    assert out.state == IN_DOUBT, out
    funds_window = _customer_total(accounts) - funds0
    pinned = _pinned(proto, accounts)

    t0 = time.perf_counter()
    by = proto.transfer(
        src, dst_bystander, AmountPaise(cfg.amount_minor // 10 or 1),
        lock_timeout_ms=cfg.bystander_timeout_ms,
    )
    by_wait = (time.perf_counter() - t0) * 1000

    t1 = time.perf_counter()
    proto.recover()
    recovery_ms = (time.perf_counter() - t1) * 1000

    extra = 0
    if by.state == SETTLED:
        extra = 0  # bystander moves funds between customers; total is unchanged
    return CrashResult(
        protocol=proto.name,
        crash_point=_CRASH_POINT[proto.name],
        outcome_at_crash=out.state,
        customer_funds_delta_in_window=funds_window,
        partial_posting_visible=funds_window != 0,
        resources_pinned_in_window=pinned,
        bystander_state=by.state,
        bystander_wait_ms=round(by_wait, 1),
        recovery_ms=round(recovery_ms, 1),
        customer_funds_delta_after=_customer_total(accounts) - funds0 - extra,
        clearing_delta_after=_clearing_total() - clearing0,
        unresolved_after=_unresolved(proto),
    )


def _failure(proto: TransferProtocol, cfg: ComparisonConfig) -> FailureResult:
    src = _new_account("ledger-1", cfg.funding_minor)
    dst = _new_account("ledger-2", 0)
    set_account_status(settings.ledger2_db_url, dst, AccountStatus.CLOSED, reason="comparison")
    accounts = {src: "ledger-1", dst: "ledger-2"}
    funds0 = _customer_total(accounts)
    clearing0 = _clearing_total()
    journals0 = _journal_count()

    out = proto.transfer(src, dst, AmountPaise(cfg.amount_minor))
    funds_delta = _customer_total(accounts) - funds0
    clearing_delta = _clearing_total() - clearing0
    return FailureResult(
        protocol=proto.name,
        final_state=out.state,
        customer_funds_delta=funds_delta,
        clearing_delta=clearing_delta,
        journals_written=_journal_count() - journals0,
        atomic=out.state == CANCELLED and funds_delta == 0 and clearing_delta == 0,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def run_comparison(cfg: ComparisonConfig | None = None) -> ComparisonReport:
    cfg = cfg or ComparisonConfig()
    _prov = collect_provenance()
    urls = _urls()
    available: dict[str, TransferProtocol] = {
        "TCC": TccProtocol(settings.coordinator_db_url, urls),
        "XA-2PC": XaProtocol(urls),
        "Saga": SagaProtocol(urls),
    }
    protos = [available[n] for n in cfg.protocols]
    throughput = _throughput_all(protos, cfg)
    crash = [_crash(p, cfg) for p in protos]
    failure = [_failure(p, cfg) for p in protos]
    with psycopg.connect(settings.ledger1_db_url) as conn:
        pg = conn.execute("SHOW server_version;").fetchone()
    return ComparisonReport(
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        git_sha=_prov.git_sha,
        git_tree=_prov.git_tree,
        working_tree_clean=_prov.working_tree_clean,
        environment={
            "python": platform.python_version(),
            "platform": platform.platform(),
            "postgres": str(pg[0]) if pg else "unknown",
            "cpu_count": str(os.cpu_count()),
            "machine": platform.machine(),
        },
        config=cfg,
        throughput=throughput,
        crash=crash,
        failure=failure,
    )


def report_json(report: ComparisonReport) -> str:
    return json.dumps(report.model_dump(), indent=2, sort_keys=True) + "\n"


__all__ = ["ComparisonConfig", "ComparisonReport", "run_comparison", "report_json",
           "statistics"]
