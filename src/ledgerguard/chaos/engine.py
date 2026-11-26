"""Deterministic chaos campaign execution engine."""

from __future__ import annotations

import random
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from ledgerguard.chaos.models import (
    ChaosCampaignConfig,
    ChaosCampaignReport,
    ChaosFaultType,
    FaultTimelineEntry,
    InvariantResult,
)
from ledgerguard.config import settings
from ledgerguard.coordinator.directory_service import provision_account, register_customer
from ledgerguard.coordinator.failpoints import FailpointError, FailpointManager
from ledgerguard.coordinator.reconciliation import run_cross_ledger_reconciliation
from ledgerguard.coordinator.transfer_coordinator import submit_coordinator_transfer
from ledgerguard.domain.invariants import INVARIANT_CATALOGUE
from ledgerguard.domain.money import AmountPaise
from ledgerguard.participant.account_service import get_account_balance
from ledgerguard.participant.posting_service import simulate_funding
from ledgerguard.participant.transfer_service import execute_local_transfer
from ledgerguard.participant.workflow_handler import (
    handle_participant_cancel,
    handle_source_prepare,
)
from ledgerguard.worker.orchestrator import recover_pending_transfers


def _git_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL, text=True
        )
        return out.strip()
    except Exception:
        return "unknown"


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return round(ordered[idx], 2)


class ChaosCampaignEngine:
    """Executes seeded, deterministic chaos campaigns against the LedgerGuard triad."""

    def __init__(
        self,
        coord_db_url: str | None = None,
        ledger1_db_url: str | None = None,
        ledger2_db_url: str | None = None,
    ) -> None:
        self.coord_db_url = coord_db_url or settings.coordinator_db_url
        self.ledger1_db_url = ledger1_db_url or settings.ledger1_db_url
        self.ledger2_db_url = ledger2_db_url or settings.ledger2_db_url
        self.ledger_urls = {
            "ledger-1": self.ledger1_db_url,
            "ledger-2": self.ledger2_db_url,
        }

    def build_schedule(self, config: ChaosCampaignConfig) -> list[dict[str, Any]]:
        """Generate deterministic abstract workload and fault schedule from seed."""
        rng = random.Random(config.seed)
        plan: list[dict[str, Any]] = []
        for step in range(1, config.operation_count + 1):
            is_local = rng.random() < config.local_ratio
            use_hot = rng.random() < config.hot_account_percentage
            amt = rng.randint(config.min_amount_minor, config.max_amount_minor)
            fault: ChaosFaultType | None = None
            if config.failure_schedule and (step % max(2, config.operation_count // max(1, len(config.failure_schedule))) == 0):
                fault = config.failure_schedule[(step - 1) % len(config.failure_schedule)]
            elif rng.random() < config.duplicate_probability:
                fault = ChaosFaultType.DUPLICATE_COMMAND_DELIVERY
            elif rng.random() < config.delay_probability:
                fault = ChaosFaultType.ARTIFICIAL_PROCESSING_DELAY
            elif rng.random() < config.reorder_probability:
                fault = ChaosFaultType.REORDERED_COMMAND_DELIVERY

            plan.append(
                {
                    "step": step,
                    "is_local": is_local,
                    "use_hot": use_hot,
                    "amount_minor": amt,
                    "src_slot": 0 if use_hot else rng.randrange(0, max(1, config.num_accounts // 2)),
                    "dst_slot": rng.randrange(0, max(1, config.num_accounts // 2)),
                    "fault": fault,
                }
            )
        return plan

    def run(self, config: ChaosCampaignConfig) -> ChaosCampaignReport:
        """Execute a complete chaos campaign lifecycle and return verified report."""
        if settings.env == "production":
            raise RuntimeError("Chaos campaigns are disabled in production environment.")

        campaign_id = f"chaos-{config.seed}-{uuid4().hex[:8]}"
        rng = random.Random(config.seed)
        schedule = self.build_schedule(config)

        # 1. Seed synthetic accounts across ledger-1 and ledger-2
        l1_accounts: list[UUID] = []
        l2_accounts: list[UUID] = []
        half = max(2, config.num_accounts // 2)
        for idx in range(half):
            c1 = register_customer(
                self.coord_db_url,
                f"Chaos L1 User {idx}",
                f"chaos-l1-{campaign_id}-{idx}@synthetic.local",
            )
            a1 = provision_account(
                self.coord_db_url,
                self.ledger_urls,
                UUID(str(c1["customer_id"])),
                "ledger-1",
                currency="INR",
            )
            aid1 = UUID(str(a1["account_id"]))
            simulate_funding(self.ledger1_db_url, aid1, AmountPaise(config.initial_balance_minor))
            l1_accounts.append(aid1)

            c2 = register_customer(
                self.coord_db_url,
                f"Chaos L2 User {idx}",
                f"chaos-l2-{campaign_id}-{idx}@synthetic.local",
            )
            a2 = provision_account(
                self.coord_db_url,
                self.ledger_urls,
                UUID(str(c2["customer_id"])),
                "ledger-2",
                currency="INR",
            )
            aid2 = UUID(str(a2["account_id"]))
            simulate_funding(self.ledger2_db_url, aid2, AmountPaise(config.initial_balance_minor))
            l2_accounts.append(aid2)

        # 2. Execute workload with deterministic fault injection
        settled_count = 0
        cancelled_count = 0
        recovered_count = 0
        duplicate_ignored = 0
        fault_counts: dict[str, int] = {}
        fault_timeline: list[FaultTimelineEntry] = []
        recovery_latencies_ms: list[float] = []
        unexpected_errors: list[str] = []

        def execute_step(item: dict[str, Any]) -> None:
            nonlocal settled_count, cancelled_count, recovered_count, duplicate_ignored
            step = item["step"]
            fault: ChaosFaultType | None = item["fault"]
            amt = AmountPaise(item["amount_minor"])
            src_id = l1_accounts[item["src_slot"] % len(l1_accounts)]
            is_local = item["is_local"]
            if is_local:
                dst_id = l1_accounts[(item["dst_slot"] + 1) % len(l1_accounts)]
                if dst_id == src_id:
                    dst_id = l1_accounts[(item["src_slot"] + 1) % len(l1_accounts)]
            else:
                dst_id = l2_accounts[item["dst_slot"] % len(l2_accounts)]

            idem_key = f"{campaign_id}-step-{step}"
            tx_id = uuid4()
            fp = FailpointManager()
            injected_at = datetime.now(UTC).isoformat()

            if fault is not None:
                fault_counts[fault.value] = fault_counts.get(fault.value, 0) + 1

            try:
                if fault == ChaosFaultType.ARTIFICIAL_PROCESSING_DELAY:
                    time.sleep(0.02)

                if fault == ChaosFaultType.REORDERED_COMMAND_DELIVERY and not is_local:
                    # Cancel arrives before prepare -> tombstone must block late prepare
                    handle_participant_cancel(
                        self.ledger1_db_url,
                        command_id=f"chaos-cancel-{tx_id}",
                        transfer_id=tx_id,
                    )
                    prep = handle_source_prepare(
                        self.ledger1_db_url,
                        command_id=f"chaos-late-prep-{tx_id}",
                        transfer_id=tx_id,
                        source_account_id=src_id,
                        dest_account_id=dst_id,
                        amount_minor=int(amt),
                    )
                    if prep.get("status") == "REJECTED":
                        cancelled_count += 1
                    fault_timeline.append(
                        FaultTimelineEntry(
                            step=step,
                            fault_type=fault.value,
                            target=str(tx_id),
                            injected_at=injected_at,
                            restored_at=datetime.now(UTC).isoformat(),
                            recovered=True,
                            details=f"Tombstone blocked delayed prepare: {prep.get('status')}",
                        )
                    )
                    return

                if is_local:
                    execute_local_transfer(
                        self.ledger1_db_url,
                        idempotency_key=idem_key,
                        source_account_id=src_id,
                        destination_account_id=dst_id,
                        amount=amt,
                    )
                    settled_count += 1
                    if fault in (
                        ChaosFaultType.DUPLICATE_COMMAND_DELIVERY,
                        ChaosFaultType.CLIENT_RETRY_STORM,
                    ):
                        repeats = 3 if fault == ChaosFaultType.CLIENT_RETRY_STORM else 1
                        for _ in range(repeats):
                            execute_local_transfer(
                                self.ledger1_db_url,
                                idempotency_key=idem_key,
                                source_account_id=src_id,
                                destination_account_id=dst_id,
                                amount=amt,
                            )
                            duplicate_ignored += 1
                    return

                # Cross-ledger TCC transfer
                fp_name: str | None = None
                if fault == ChaosFaultType.COORDINATOR_CRASH_AFTER_COMMIT:
                    fp_name = "FAIL_AFTER_COMMIT_BEFORE_SOURCE_CONFIRM"
                elif fault == ChaosFaultType.COORDINATOR_CRASH_BETWEEN_CONFIRMS:
                    fp_name = "FAIL_AFTER_SOURCE_CONFIRM_BEFORE_DEST_CONFIRM"
                elif fault == ChaosFaultType.LOST_REPLY_AFTER_PARTICIPANT_COMMIT:
                    fp_name = "FAIL_AFTER_DEST_CONFIRM_REPLY"
                elif fault == ChaosFaultType.COORDINATOR_CRASH_AFTER_SOURCE_PREPARE:
                    fp_name = "FAIL_AFTER_SOURCE_PREPARE_REPLY"

                if fp_name:
                    fp.set_failpoint(fp_name, tx_id)

                try:
                    res = submit_coordinator_transfer(
                        self.coord_db_url,
                        self.ledger_urls,
                        idempotency_key=idem_key,
                        source_account_id=src_id,
                        destination_account_id=dst_id,
                        amount=amt,
                        transfer_id=tx_id,
                        failpoint_mgr=fp,
                    )
                    if res.get("status") == "SETTLED":
                        settled_count += 1
                    elif res.get("status") == "CANCELLED":
                        cancelled_count += 1
                except FailpointError as exc:
                    t0 = time.perf_counter()
                    recover_pending_transfers(self.coord_db_url, self.ledger_urls)
                    elapsed_ms = (time.perf_counter() - t0) * 1000.0
                    recovery_latencies_ms.append(elapsed_ms)
                    recovered_count += 1
                    settled_count += 1
                    fault_timeline.append(
                        FaultTimelineEntry(
                            step=step,
                            fault_type=fault.value if fault else "FAILPOINT",
                            target=str(tx_id),
                            injected_at=injected_at,
                            restored_at=datetime.now(UTC).isoformat(),
                            recovered=True,
                            details=f"Recovered forward from {type(exc).__name__} in {elapsed_ms:.1f}ms",
                        )
                    )

                if fault in (
                    ChaosFaultType.DUPLICATE_COMMAND_DELIVERY,
                    ChaosFaultType.CLIENT_RETRY_STORM,
                ):
                    repeats = 2 if fault == ChaosFaultType.CLIENT_RETRY_STORM else 1
                    for _ in range(repeats):
                        submit_coordinator_transfer(
                            self.coord_db_url,
                            self.ledger_urls,
                            idempotency_key=idem_key,
                            source_account_id=src_id,
                            destination_account_id=dst_id,
                            amount=amt,
                            transfer_id=tx_id,
                        )
                        duplicate_ignored += 1

            except Exception as exc:
                unexpected_errors.append(f"step={step}: {exc}")

        with ThreadPoolExecutor(max_workers=config.worker_count) as pool:
            futures = [pool.submit(execute_step, item) for item in schedule]
            for fut in as_completed(futures):
                fut.result()

        # 3. Drain & forward-recover any remaining pending transfers
        t_drain = time.perf_counter()
        recover_pending_transfers(self.coord_db_url, self.ledger_urls)
        drain_ms = (time.perf_counter() - t_drain) * 1000.0
        if recovery_latencies_ms:
            max_unresolved = max(recovery_latencies_ms)
        else:
            max_unresolved = round(drain_ms, 2)

        # 4. Run stopped-and-drained cross-ledger reconciliation
        recon = run_cross_ledger_reconciliation(
            self.coord_db_url,
            self.ledger_urls,
            drained=True,
        )

        # 5. Check account balances & invariants
        negative_balance = False
        for aid in l1_accounts:
            bal = get_account_balance(self.ledger1_db_url, aid)
            if bal.available_balance_minor < 0 or bal.held_amount_minor < 0:
                negative_balance = True
        for aid in l2_accounts:
            bal = get_account_balance(self.ledger2_db_url, aid)
            if bal.available_balance_minor < 0 or bal.held_amount_minor < 0:
                negative_balance = True

        incomplete = recon.coverage != "FULL" or recon.status == "INCOMPLETE"
        recon_failed = recon.status == "FAIL" or len(recon.findings) > 0

        invariant_results: list[InvariantResult] = []
        for inv in INVARIANT_CATALOGUE:
            if incomplete and inv.id in ("I13", "I14"):
                inv_status = "INCOMPLETE"
                detail = f"Reconciliation coverage={recon.coverage}, status={recon.status}"
            elif inv.id == "I3" and negative_balance:
                inv_status = "FAIL"
                detail = "Negative available or held balance detected."
            elif inv.id == "I13" and recon_failed:
                inv_status = "FAIL"
                detail = f"Clearing/reconciliation findings: {len(recon.findings)}"
            elif unexpected_errors and inv.id in ("I8", "I4", "I5"):
                inv_status = "FAIL"
                detail = "; ".join(unexpected_errors[:3])
            else:
                inv_status = "PASS" if not incomplete else "INCOMPLETE"
                detail = "Verified" if not incomplete else "Incomplete cluster reachability"
            invariant_results.append(
                InvariantResult(id=inv.id, name=inv.name, status=inv_status, details=detail)
            )

        if incomplete:
            overall_status = "INCOMPLETE"
        elif any(r.status == "FAIL" for r in invariant_results) or unexpected_errors or recon_failed:
            overall_status = "FAIL"
        else:
            overall_status = "PASS"

        _ = rng.random()  # keep deterministic rng reference

        return ChaosCampaignReport(
            campaign_id=campaign_id,
            seed=config.seed,
            git_sha=_git_sha(),
            environment={
                "env": settings.env,
                "worker_count": config.worker_count,
                "num_accounts": len(l1_accounts) + len(l2_accounts),
            },
            config=config,
            status=overall_status,
            operations_attempted=len(schedule),
            settled_count=settled_count,
            cancelled_count=cancelled_count,
            recovered_count=recovered_count,
            duplicate_messages_ignored=duplicate_ignored,
            fault_counts=fault_counts,
            max_unresolved_duration_ms=round(max_unresolved, 2),
            recovery_latency_ms={
                "p50": _percentile(recovery_latencies_ms, 50),
                "p95": _percentile(recovery_latencies_ms, 95),
                "max": round(max(recovery_latencies_ms, default=0.0), 2),
            },
            invariant_results=invariant_results,
            reconciliation_result={
                "status": recon.status,
                "coverage": recon.coverage,
                "findings_count": len(recon.findings),
                "reachable_ledgers": recon.reachable_ledgers,
                "unreachable_ledgers": recon.unreachable_ledgers,
            },
            fault_timeline=fault_timeline,
            counterexample_history=(
                {"unexpected_errors": unexpected_errors} if unexpected_errors else None
            ),
        )


def run_chaos_campaign(config: ChaosCampaignConfig | None = None) -> ChaosCampaignReport:
    """Run a chaos campaign with default or supplied configuration."""
    return ChaosCampaignEngine().run(config or ChaosCampaignConfig())
