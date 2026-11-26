"""Real-fault scenarios: SIGKILL, partitions, resets, latency, API crash, container crash."""

from __future__ import annotations

import json
import os
import platform
import random
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import psycopg
from pydantic import BaseModel, Field

from ledgerguard.config import settings
from ledgerguard.faults.harness import (
    FaultEnv,
    InvariantResult,
    WorkerProcess,
    check_invariants,
    direct_ledger_urls,
    new_account,
    recover_until_drained,
    transfer_state,
)
from ledgerguard.participant.reconciliation_service import run_local_reconciliation

REPO_ROOT = Path(__file__).resolve().parents[3]


class ScenarioResult(BaseModel):
    name: str
    faults: list[str]
    transfers: int = 0
    settled: int = 0
    cancelled: int = 0
    recovered_by_recovery_loop: int = 0
    facts: dict[str, Any] = Field(default_factory=dict)
    invariants: list[InvariantResult] = Field(default_factory=list)
    seconds: float = 0.0

    @property
    def passed(self) -> bool:
        return all(i.passed for i in self.invariants)


class FaultCampaignReport(BaseModel):
    schema_version: int = 1
    generated_at: str
    git_sha: str
    seed: int
    environment: dict[str, str]
    scenarios: list[ScenarioResult]

    @property
    def passed(self) -> bool:
        return all(s.passed for s in self.scenarios)

    def to_markdown(self) -> str:
        lines = [
            "# Real fault-injection campaign",
            "",
            f"- Generated `{self.generated_at}` at commit `{self.git_sha}`, seed `{self.seed}`",
            f"- Environment: {self.environment}",
            f"- **Overall: {'PASS' if self.passed else 'FAIL'}**",
            "",
            "| Scenario | Faults injected | Transfers | Settled | Cancelled | Recovered | Invariants | Key facts |",
            "|---|---|---:|---:|---:|---:|---|---|",
        ]
        for s in self.scenarios:
            ok = sum(1 for i in s.invariants if i.passed)
            facts = "; ".join(f"{k}={v}" for k, v in s.facts.items())
            lines.append(
                f"| {s.name} | {', '.join(s.faults)} | {s.transfers} | {s.settled} | {s.cancelled} | "
                f"{s.recovered_by_recovery_loop} | {ok}/{len(s.invariants)} "
                f"{'PASS' if s.passed else 'FAIL'} | {facts} |"
            )
        lines += ["", "## Invariants checked after recovery (every scenario)", ""]
        for name in dict.fromkeys(i.name for s in self.scenarios for i in s.invariants):
            lines.append(f"- `{name}`")
        failures = [(s.name, i) for s in self.scenarios for i in s.invariants if not i.passed]
        if failures:
            lines += ["", "## Failures", ""]
            lines += [f"- {n}: `{i.name}` - {i.detail}" for n, i in failures]
        return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _finish(name: str, faults: list[str], env: FaultEnv, t0: float, facts: dict[str, Any],
            recovered: int) -> ScenarioResult:
    rows = env.transfer_rows()
    res = ScenarioResult(
        name=name, faults=faults, transfers=len(rows),
        settled=sum(1 for _, s in rows if s == "SETTLED"),
        cancelled=sum(1 for _, s in rows if s in ("CANCELLED", "REJECTED")),
        recovered_by_recovery_loop=recovered, facts=facts,
        invariants=check_invariants(env), seconds=round(time.perf_counter() - t0, 2),
    )
    return res


def _run(name: str, faults: list[str], body: Callable[[FaultEnv, dict[str, Any]], None],
         pairs: int = 3) -> ScenarioResult:
    env = FaultEnv.create(pair_count=pairs)
    facts: dict[str, Any] = {}
    t0 = time.perf_counter()
    try:
        body(env, facts)
        env.heal_all()
        recovered = recover_until_drained(env)
        return _finish(name, faults, env, t0, facts, recovered)
    finally:
        env.close()


# ---------------------------------------------------------------------------
# scenarios
# ---------------------------------------------------------------------------


def kill_after_durable_commit(rounds: int = 4) -> ScenarioResult:
    """SIGKILL the worker after the COMMIT decision is durable but before settlement."""

    def body(env: FaultEnv, facts: dict[str, Any]) -> None:
        env.proxies["ledger-1"].set_latency(120)  # widen the crash window deterministically
        hits = 0
        for _ in range(rounds):
            w = WorkerProcess(env, count=1)
            try:
                w.wait_for(lambda w=w: w.count("start") >= 1, 30)
                tid = w.started_ids()[0]
                seen = w.wait_for(lambda tid=tid: transfer_state(tid)[1] == "COMMIT", 30,
                                  poll_s=0.002)
                state_at_kill = transfer_state(tid)[0]
                w.kill()
                if seen and state_at_kill not in ("SETTLED", "CANCELLED"):
                    hits += 1
            finally:
                w.kill()
        facts["kills_inside_commit_window"] = f"{hits}/{rounds}"

    return _run("SIGKILL after durable COMMIT", ["kill -9 worker", "ledger-1 +120ms"], body, pairs=1)


def random_kill_burst(seed: int, rounds: int = 4) -> ScenarioResult:
    """Repeatedly SIGKILL a worker at random instants during a transfer burst."""

    def body(env: FaultEnv, facts: dict[str, Any]) -> None:
        rng = random.Random(seed)
        kills = 0
        for _ in range(rounds):
            w = WorkerProcess(env, count=12, pause_ms=10)
            try:
                w.wait_for(lambda w=w: w.count("ready") >= 1, 30)
                time.sleep(rng.uniform(0.15, 1.2))
                if not w.finished():
                    kills += 1
                w.kill()
            finally:
                w.kill()
        facts["worker_kills"] = kills

    return _run("Random SIGKILL burst", [f"kill -9 x{rounds} (seeded)"], body)


def latency_burst() -> ScenarioResult:
    """Run a burst with 150 ms of latency on both ledgers (slow, not broken)."""

    def body(env: FaultEnv, facts: dict[str, Any]) -> None:
        for lid in ("ledger-1", "ledger-2"):
            env.proxies[lid].set_latency(150)
        w = WorkerProcess(env, count=8)
        finished = w.wait(180)
        facts["worker_finished"] = finished
        facts["done_events"] = w.count("done")
        if not finished:
            w.kill()

    return _run("Network latency", ["ledger-1 +150ms", "ledger-2 +150ms"], body)


def partition_destination() -> ScenarioResult:
    """Black-hole the destination ledger mid-burst (hanging connections), then kill and heal."""

    def body(env: FaultEnv, facts: dict[str, Any]) -> None:
        w = WorkerProcess(env, count=12, pause_ms=20)
        try:
            w.wait_for(lambda: w.count("done") >= 2, 60)
            env.proxies["ledger-2"].blackhole()
            before = w.count("done")
            time.sleep(3.0)
            facts["progress_during_partition"] = w.count("done") - before
            facts["bytes_dropped_by_partition"] = env.proxies["ledger-2"].bytes_dropped
            w.kill()  # the supervisor gives up on the hung worker
        finally:
            w.kill()

    return _run("Partition of destination ledger", ["ledger-2 black-hole", "kill -9 hung worker"], body)


def connection_reset_storm(seed: int) -> ScenarioResult:
    """Randomly reset every live TCP connection to all three databases during a burst."""

    def body(env: FaultEnv, facts: dict[str, Any]) -> None:
        rng = random.Random(seed)
        w = WorkerProcess(env, count=12, pause_ms=10)
        stop = threading.Event()
        resets = [0]

        def storm() -> None:
            while not stop.is_set():
                time.sleep(rng.uniform(0.08, 0.3))
                p = env.proxies[rng.choice(["coordinator", "ledger-1", "ledger-2"])]
                resets[0] += p.sever()

        t = threading.Thread(target=storm, daemon=True)
        t.start()
        try:
            w.wait(8)
        finally:
            stop.set()
            t.join(timeout=5)
            env.heal_all()
        facts["connections_reset"] = resets[0]
        if not w.wait(90):
            w.kill()
        facts["worker_errors"] = w.count("error")

    return _run("TCP reset storm", ["RST on live connections, random link"], body)


def api_kill_idempotent_replay(seed: int, n: int = 30) -> ScenarioResult:
    """SIGKILL the API mid-burst; replaying the same Idempotency-Keys must apply each once."""
    rng = random.Random(seed)
    src = new_account("ledger-1", 1_000_000)
    dst = new_account("ledger-1", 0)
    urls = direct_ledger_urls()
    from ledgerguard.participant.account_service import get_account_balance
    s0 = get_account_balance(urls["ledger-1"], src).posted_balance_minor
    d0 = get_account_balance(urls["ledger-1"], dst).posted_balance_minor
    t0 = time.perf_counter()

    import socket
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    headers = {"Authorization": f"Bearer {settings.api_bearer_token}"}

    def start_api() -> subprocess.Popen[bytes]:
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "ledgerguard.api.app:app", "--host", "127.0.0.1",
             "--port", str(port), "--log-level", "warning"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env={**os.environ, "LEDGERGUARD_COOKIE_SECURE": "false"}, cwd=REPO_ROOT,
        )
        for _ in range(200):
            try:
                if httpx.get(f"{base}/health", timeout=1).status_code == 200:
                    return proc
            except httpx.HTTPError:
                time.sleep(0.1)
        proc.kill()
        raise RuntimeError("API did not start")

    run_nonce = uuid4().hex[:12]  # keys must be unique per run: reuse with new accounts is a (correct) 409
    keys = [f"api-fault-{run_nonce}-{i}" for i in range(n)]
    body = {"source_account_id": str(src), "destination_account_id": str(dst), "amount_minor": 100}

    def post(key: str) -> tuple[str, str | None]:
        try:
            r = httpx.post(f"{base}/v1/transfers", json=body, timeout=10,
                           headers={**headers, "Idempotency-Key": key})
            return key, r.json().get("transfer_id") if r.status_code == 200 else None
        except httpx.HTTPError:
            return key, None

    api = start_api()
    acked: dict[str, str | None] = {}
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(post, k) for k in keys]
            time.sleep(rng.uniform(0.25, 0.6))
            api.kill()  # SIGKILL mid-burst
            api.wait(timeout=10)
            for f in futures:
                k, tid = f.result()
                acked[k] = tid
    finally:
        if api.poll() is None:
            api.kill()
    acked_before = sum(1 for v in acked.values() if v)

    api = start_api()
    try:
        replay1 = dict(post(k) for k in keys)
        replay2 = dict(post(k) for k in keys)
    finally:
        api.kill()
        api.wait(timeout=10)

    s1 = get_account_balance(urls["ledger-1"], src).posted_balance_minor
    d1 = get_account_balance(urls["ledger-1"], dst).posted_balance_minor
    ids = [v for v in replay1.values() if v]
    with psycopg.connect(settings.ledger1_db_url) as conn:
        journals = conn.execute(
            "SELECT count(*) FROM journal_headers WHERE transfer_id = ANY(%s)", (ids,)
        ).fetchone()[0]  # type: ignore[index]
    recon = run_local_reconciliation(settings.ledger1_db_url)
    invariants = [
        InvariantResult(name="every_key_succeeds_on_replay", passed=len(ids) == n,
                        detail=f"{len(ids)}/{n} keys returned a transfer"),
        InvariantResult(name="replay_returns_same_transfer", passed=replay1 == replay2,
                        detail="second replay identical to first"),
        InvariantResult(name="each_key_applied_exactly_once",
                        passed=(s0 - s1) == n * 100 and (d1 - d0) == n * 100 and journals == n,
                        detail=f"source -{s0 - s1}, dest +{d1 - d0}, journals={journals}, expected {n * 100}/{n}"),
        InvariantResult(name="acknowledged_transfers_preserved",
                        passed=all(replay1[k] == v for k, v in acked.items() if v),
                        detail=f"{acked_before} acks before the crash all match after restart"),
        InvariantResult(name="ledger_reconciliation", passed=recon.status == "PASS",
                        detail=f"status={recon.status}"),
    ]
    return ScenarioResult(
        name="API SIGKILL + idempotent replay", faults=["kill -9 API mid-burst", "client retries"],
        transfers=n, settled=len(ids), facts={"acked_before_crash": acked_before,
                                              "unacked_replayed": n - acked_before},
        invariants=invariants, seconds=round(time.perf_counter() - t0, 2),
    )


def _container_id(service: str) -> str:
    out = subprocess.run(["docker", "compose", "ps", "-q", service], cwd=REPO_ROOT,
                         capture_output=True, text=True, check=True).stdout.strip()
    if not out:
        raise RuntimeError(f"compose service {service} is not running")
    return out.splitlines()[0]


def _wait_db_up(url: str, timeout_s: int = 90) -> None:
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        try:
            with psycopg.connect(url, connect_timeout=2) as conn:
                conn.execute("SELECT 1")
            return
        except psycopg.Error:
            time.sleep(0.5)
    raise RuntimeError("database did not come back")


def postgres_crash(service: str, url: str) -> ScenarioResult:
    """SIGKILL a PostgreSQL server (real crash recovery on restart) during a burst."""

    def body(env: FaultEnv, facts: dict[str, Any]) -> None:
        cid = _container_id(service)
        w = WorkerProcess(env, count=12, pause_ms=30)
        try:
            w.wait_for(lambda: w.count("done") >= 2, 60)
            subprocess.run(["docker", "kill", "-s", "KILL", cid], check=True, capture_output=True)
            facts["container_killed"] = service
            time.sleep(2.0)
            subprocess.run(["docker", "start", cid], check=True, capture_output=True)
            _wait_db_up(url)
            facts["worker_survived_outage"] = w.wait(120)
        finally:
            w.kill()

    return _run(f"PostgreSQL SIGKILL ({service})", [f"docker kill -s KILL {service}", "restart"], body)


# ---------------------------------------------------------------------------
# campaign
# ---------------------------------------------------------------------------


def _git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, cwd=REPO_ROOT).strip()
    except Exception:
        return "unknown"


def run_campaign(seed: int = 42, include_containers: bool = False) -> FaultCampaignReport:
    results = [
        kill_after_durable_commit(),
        random_kill_burst(seed),
        latency_burst(),
        partition_destination(),
        connection_reset_storm(seed),
        api_kill_idempotent_replay(seed),
    ]
    if include_containers:
        results.append(postgres_crash("postgres-ledger2", settings.ledger2_db_url))
        results.append(postgres_crash("postgres-coordinator", settings.coordinator_db_url))
    with psycopg.connect(settings.ledger1_db_url) as conn:
        pg = conn.execute("SHOW server_version").fetchone()
    return FaultCampaignReport(
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"), git_sha=_git_sha(), seed=seed,
        environment={"python": platform.python_version(), "platform": platform.platform(),
                     "postgres": str(pg[0]) if pg else "unknown"},
        scenarios=results,
    )


def report_json(report: FaultCampaignReport) -> str:
    return json.dumps(report.model_dump(), indent=2, sort_keys=True) + "\n"


__all__ = ["FaultCampaignReport", "ScenarioResult", "UUID", "run_campaign", "report_json"]
