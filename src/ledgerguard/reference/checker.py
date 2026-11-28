"""History checker comparing observed cluster histories against ReferenceLedgerModel."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ledgerguard.domain.invariants import INVARIANTS_BY_ID
from ledgerguard.reference.history import ExecutionHistory, HistoryEvent, ObservedClusterState
from ledgerguard.reference.model import OperationOutcome, ReferenceLedgerModel


class DivergenceDetail(BaseModel):
    """Structured explanation of the first detected divergence."""

    failed_invariant: str
    invariant_description: str
    first_divergent_operation_id: str | None = None
    logical_step: int | None = None
    reason: str
    expected_state: dict[str, Any] = Field(default_factory=dict)
    actual_state: dict[str, Any] = Field(default_factory=dict)
    minimal_relevant_history: list[dict[str, Any]] = Field(default_factory=list)
    reproduction_seed: int


class CheckReport(BaseModel):
    """Result of checking an ExecutionHistory against the reference model."""

    history_id: str
    seed: int
    status: str  # PASS, FAIL, INCOMPLETE
    events_checked: int
    divergence: DivergenceDetail | None = None


def _invariant_desc(inv_id: str) -> str:
    spec = INVARIANTS_BY_ID.get(inv_id)
    return spec.description if spec else inv_id


def _minimal_history(events: list[HistoryEvent], event: HistoryEvent | None) -> list[dict[str, Any]]:
    if event is None:
        return [e.model_dump(exclude={"observed_state_after"}) for e in events[-10:]]
    tid = event.request_parameters.get("transfer_id") or event.request_parameters.get("original_transfer_id")
    aids = {
        event.request_parameters.get("account_id"),
        event.request_parameters.get("source_account_id"),
        event.request_parameters.get("destination_account_id"),
    } - {None}
    relevant: list[dict[str, Any]] = []
    for e in events:
        if e.logical_step > event.logical_step:
            continue
        e_tid = e.request_parameters.get("transfer_id") or e.request_parameters.get("original_transfer_id")
        e_aids = {
            e.request_parameters.get("account_id"),
            e.request_parameters.get("source_account_id"),
            e.request_parameters.get("destination_account_id"),
        } - {None}
        if (tid and e_tid == tid) or (aids & e_aids) or e.operation_id == event.operation_id:
            relevant.append(e.model_dump(exclude={"observed_state_after"}))
    return relevant


def _compare_cluster_state(
    model: ReferenceLedgerModel,
    observed: ObservedClusterState,
    events: list[HistoryEvent],
    event: HistoryEvent | None,
    seed: int,
) -> DivergenceDetail | None:
    required_dbs = {"coordinator", "ledger-1", "ledger-2"}
    if not required_dbs.issubset(set(observed.reachable_databases)):
        return DivergenceDetail(
            failed_invariant="I14",
            invariant_description=_invariant_desc("I14"),
            first_divergent_operation_id=event.operation_id if event else None,
            logical_step=event.logical_step if event else None,
            reason=f"Incomplete database reachability: {observed.reachable_databases}",
            expected_state={"reachable_databases": sorted(required_dbs)},
            actual_state={"reachable_databases": sorted(observed.reachable_databases)},
            minimal_relevant_history=_minimal_history(events, event),
            reproduction_seed=seed,
        )

    # Check journal totals (I1)
    for lid in ("ledger-1", "ledger-2"):
        debits = observed.journal_debit_total_minor.get(lid, 0)
        credits = observed.journal_credit_total_minor.get(lid, 0)
        if debits != credits:
            return DivergenceDetail(
                failed_invariant="I1",
                invariant_description=_invariant_desc("I1"),
                first_divergent_operation_id=event.operation_id if event else None,
                logical_step=event.logical_step if event else None,
                reason=f"Unbalanced journal totals on {lid}: debits={debits}, credits={credits}",
                expected_state={"debits_equals_credits": True},
                actual_state={"ledger_id": lid, "debits": debits, "credits": credits},
                minimal_relevant_history=_minimal_history(events, event),
                reproduction_seed=seed,
            )

    # Check account balances (I3, posted/held/available)
    for aid, ref_acct in model.accounts.items():
        obs_acct = observed.accounts.get(aid)
        if obs_acct is None:
            return DivergenceDetail(
                failed_invariant="I13",
                invariant_description=_invariant_desc("I13"),
                first_divergent_operation_id=event.operation_id if event else None,
                logical_step=event.logical_step if event else None,
                reason=f"Account {aid} missing from observed state",
                expected_state={"account_id": aid, "posted": ref_acct.posted_balance_minor},
                actual_state={"account_id": aid, "missing": True},
                minimal_relevant_history=_minimal_history(events, event),
                reproduction_seed=seed,
            )
        if obs_acct.available_balance_minor < 0:
            return DivergenceDetail(
                failed_invariant="I3",
                invariant_description=_invariant_desc("I3"),
                first_divergent_operation_id=event.operation_id if event else None,
                logical_step=event.logical_step if event else None,
                reason=f"Negative available balance on {aid}: {obs_acct.available_balance_minor}",
                expected_state={"available_balance_minor_gte": 0},
                actual_state=obs_acct.model_dump(),
                minimal_relevant_history=_minimal_history(events, event),
                reproduction_seed=seed,
            )
        if (
            obs_acct.posted_balance_minor != ref_acct.posted_balance_minor
            or obs_acct.held_amount_minor != ref_acct.held_amount_minor
            or obs_acct.available_balance_minor != ref_acct.available_balance_minor
        ):
            return DivergenceDetail(
                failed_invariant="I13",
                invariant_description=_invariant_desc("I13"),
                first_divergent_operation_id=event.operation_id if event else None,
                logical_step=event.logical_step if event else None,
                reason=f"Balance mismatch on account {aid}",
                expected_state={
                    "account_id": aid,
                    "posted_balance_minor": ref_acct.posted_balance_minor,
                    "held_amount_minor": ref_acct.held_amount_minor,
                    "available_balance_minor": ref_acct.available_balance_minor,
                },
                actual_state=obs_acct.model_dump(),
                minimal_relevant_history=_minimal_history(events, event),
                reproduction_seed=seed,
            )

    # Check transfer states & decision monotonicity (I6, I7, I9)
    for tid, ref_tx in model.transfers.items():
        obs_tx = observed.transfers.get(tid)
        if obs_tx is None:
            continue
        if ref_tx.decision == "COMMIT" and obs_tx.decision == "CANCEL":
            return DivergenceDetail(
                failed_invariant="I6",
                invariant_description=_invariant_desc("I6"),
                first_divergent_operation_id=event.operation_id if event else None,
                logical_step=event.logical_step if event else None,
                reason=f"Durable COMMIT decision flipped to CANCEL for transfer {tid}",
                expected_state={"transfer_id": tid, "decision": "COMMIT"},
                actual_state=obs_tx.model_dump(),
                minimal_relevant_history=_minimal_history(events, event),
                reproduction_seed=seed,
            )
        if ref_tx.decision == "CANCEL" and obs_tx.decision == "COMMIT":
            return DivergenceDetail(
                failed_invariant="I7",
                invariant_description=_invariant_desc("I7"),
                first_divergent_operation_id=event.operation_id if event else None,
                logical_step=event.logical_step if event else None,
                reason=f"Durable CANCEL decision flipped to COMMIT for transfer {tid}",
                expected_state={"transfer_id": tid, "decision": "CANCEL"},
                actual_state=obs_tx.model_dump(),
                minimal_relevant_history=_minimal_history(events, event),
                reproduction_seed=seed,
            )
        if ref_tx.decision == "CANCEL" and obs_tx.state == "SETTLED":
            return DivergenceDetail(
                failed_invariant="I9",
                invariant_description=_invariant_desc("I9"),
                first_divergent_operation_id=event.operation_id if event else None,
                logical_step=event.logical_step if event else None,
                reason=f"Cancelled transfer {tid} settled unexpectedly",
                expected_state={"transfer_id": tid, "state": ref_tx.state},
                actual_state=obs_tx.model_dump(),
                minimal_relevant_history=_minimal_history(events, event),
                reproduction_seed=seed,
            )
        if obs_tx.state != ref_tx.state or obs_tx.decision != ref_tx.decision:
            return DivergenceDetail(
                failed_invariant="I6",
                invariant_description=_invariant_desc("I6"),
                first_divergent_operation_id=event.operation_id if event else None,
                logical_step=event.logical_step if event else None,
                reason=f"Intermediate transfer state mismatch for {tid}",
                expected_state={"transfer_id": tid, "state": ref_tx.state, "decision": ref_tx.decision},
                actual_state=obs_tx.model_dump(),
                minimal_relevant_history=_minimal_history(events, event),
                reproduction_seed=seed,
            )

    # Check clearing balances & unresolved holds
    for lid in ("ledger-1", "ledger-2"):
        exp_clearing = model.clearing_balances.get(lid, 0)
        act_clearing = observed.clearing_balances.get(lid, 0)
        if act_clearing != exp_clearing:
            return DivergenceDetail(
                failed_invariant="I13",
                invariant_description=_invariant_desc("I13"),
                first_divergent_operation_id=event.operation_id if event else None,
                logical_step=event.logical_step if event else None,
                reason=f"Clearing balance mismatch on {lid}",
                expected_state={"ledger_id": lid, "clearing_balance_minor": exp_clearing},
                actual_state={"ledger_id": lid, "clearing_balance_minor": act_clearing},
                minimal_relevant_history=_minimal_history(events, event),
                reproduction_seed=seed,
            )
        exp_holds = model.unresolved_holds_for_ledger(lid)
        act_holds = observed.unresolved_holds_count.get(lid, 0)
        if act_holds != exp_holds:
            return DivergenceDetail(
                failed_invariant="I10",
                invariant_description=_invariant_desc("I10"),
                first_divergent_operation_id=event.operation_id if event else None,
                logical_step=event.logical_step if event else None,
                reason=f"Unresolved holds count mismatch on {lid}",
                expected_state={"ledger_id": lid, "unresolved_holds_count": exp_holds},
                actual_state={"ledger_id": lid, "unresolved_holds_count": act_holds},
                minimal_relevant_history=_minimal_history(events, event),
                reproduction_seed=seed,
            )

    return None


class HistoryChecker:
    """Checks an ExecutionHistory step-by-step against ReferenceLedgerModel."""

    def check(self, history: ExecutionHistory) -> CheckReport:
        model = ReferenceLedgerModel()
        events = sorted(history.events, key=lambda e: e.logical_step)

        for idx, event in enumerate(events):
            outcome: OperationOutcome = model.apply(
                event.operation,
                event.request_parameters,
                fault_active=event.fault_active,
            )

            if outcome.invariant_violation:
                return CheckReport(
                    history_id=history.history_id,
                    seed=history.seed,
                    status="FAIL",
                    events_checked=idx + 1,
                    divergence=DivergenceDetail(
                        failed_invariant=outcome.invariant_violation,
                        invariant_description=_invariant_desc(outcome.invariant_violation),
                        first_divergent_operation_id=event.operation_id,
                        logical_step=event.logical_step,
                        reason=f"Protocol invariant {outcome.invariant_violation} violated during {event.operation}",
                        expected_state={"accepted": False, "error_code": outcome.error_code},
                        actual_state=event.observed_response,
                        minimal_relevant_history=_minimal_history(events, event),
                        reproduction_seed=history.seed,
                    ),
                )

            obs_accepted = event.observed_response.get("accepted")
            if obs_accepted is not None and bool(obs_accepted) != outcome.accepted:
                inv = "I4" if "idempotency_key" in event.request_parameters else (
                    "I5" if "command_id" in event.request_parameters else "I10"
                )
                return CheckReport(
                    history_id=history.history_id,
                    seed=history.seed,
                    status="FAIL",
                    events_checked=idx + 1,
                    divergence=DivergenceDetail(
                        failed_invariant=inv,
                        invariant_description=_invariant_desc(inv),
                        first_divergent_operation_id=event.operation_id,
                        logical_step=event.logical_step,
                        reason=f"Observed acceptance ({obs_accepted}) diverged from reference model ({outcome.accepted}) on {event.operation}",
                        expected_state={"accepted": outcome.accepted, "status": outcome.status},
                        actual_state=event.observed_response,
                        minimal_relevant_history=_minimal_history(events, event),
                        reproduction_seed=history.seed,
                    ),
                )

            if event.observed_state_after is not None:
                div = _compare_cluster_state(
                    model, event.observed_state_after, events, event, history.seed
                )
                if div is not None:
                    status = "INCOMPLETE" if div.failed_invariant == "I14" else "FAIL"
                    return CheckReport(
                        history_id=history.history_id,
                        seed=history.seed,
                        status=status,
                        events_checked=idx + 1,
                        divergence=div,
                    )

        if history.final_observed_state is not None:
            div = _compare_cluster_state(
                model, history.final_observed_state, events, None, history.seed
            )
            if div is not None:
                status = "INCOMPLETE" if div.failed_invariant == "I14" else "FAIL"
                return CheckReport(
                    history_id=history.history_id,
                    seed=history.seed,
                    status=status,
                    events_checked=len(events),
                    divergence=div,
                )

        return CheckReport(
            history_id=history.history_id,
            seed=history.seed,
            status="PASS",
            events_checked=len(events),
            divergence=None,
        )


def check_history(history: ExecutionHistory) -> CheckReport:
    """Convenience wrapper to check an ExecutionHistory."""
    return HistoryChecker().check(history)


def format_report_text(report: CheckReport) -> str:
    """Render a CheckReport in human-readable text."""
    lines = [
        f"History Check Report: {report.history_id}",
        f"  Status:         {report.status}",
        f"  Seed:           {report.seed}",
        f"  Events Checked: {report.events_checked}",
    ]
    if report.divergence is not None:
        d = report.divergence
        lines.extend(
            [
                f"  Failed Invariant: {d.failed_invariant} ({d.invariant_description})",
                f"  First Divergent Operation: {d.first_divergent_operation_id} (step={d.logical_step})",
                f"  Reason: {d.reason}",
                f"  Expected State: {d.expected_state}",
                f"  Actual State:   {d.actual_state}",
                f"  Minimal History Events: {len(d.minimal_relevant_history)}",
            ]
        )
    return "\n".join(lines)
