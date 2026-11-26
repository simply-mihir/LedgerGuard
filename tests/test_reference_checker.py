"""Tests for the independent reference model, canonical history checker, and Hypothesis state machine."""

from __future__ import annotations

import ast
import json
import random
import subprocess
import sys
from pathlib import Path

import pytest
from hypothesis import settings as hyp_settings
from hypothesis import strategies as st
from hypothesis.stateful import Bundle, RuleBasedStateMachine, invariant, rule

from ledgerguard.reference import (
    AbstractOperation,
    AccountSnapshot,
    ExecutionHistory,
    HistoryEvent,
    ObservedClusterState,
    ReferenceLedgerModel,
    TransferSnapshot,
    check_history,
    format_report_text,
)


def _generate_seeded_history(seed: int) -> ExecutionHistory:
    """Generate a deterministic valid cross-ledger & local execution history from a seed."""
    rng = random.Random(seed)
    model = ReferenceLedgerModel()
    events: list[HistoryEvent] = []
    step = 0

    def record(op: str, params: dict, participant: str = "coordinator", fault: str | None = None) -> dict:
        nonlocal step
        step += 1
        out = model.apply(op, params, fault_active=fault)
        snap = ObservedClusterState(
            accounts={
                aid: AccountSnapshot(
                    account_id=aid,
                    ledger_id=acc.ledger_id,
                    posted_balance_minor=acc.posted_balance_minor,
                    held_amount_minor=acc.held_amount_minor,
                    available_balance_minor=acc.available_balance_minor,
                    status=acc.status,
                )
                for aid, acc in model.accounts.items()
            },
            transfers={
                tid: TransferSnapshot(
                    transfer_id=tid,
                    state=tx.state,
                    decision=tx.decision,
                    source_confirmed=tx.source_confirmed,
                    destination_confirmed=tx.destination_confirmed,
                    amount_minor=tx.amount_minor,
                    reversed=tx.reversed,
                )
                for tid, tx in model.transfers.items()
            },
            clearing_balances=dict(model.clearing_balances),
            journal_debit_total_minor=dict(model.journal_debits),
            journal_credit_total_minor=dict(model.journal_credits),
            unresolved_holds_count={
                "ledger-1": model.unresolved_holds_for_ledger("ledger-1"),
                "ledger-2": model.unresolved_holds_for_ledger("ledger-2"),
            },
        )
        resp = {"accepted": out.accepted, "status": out.status, "error_code": out.error_code}
        events.append(
            HistoryEvent(
                operation_id=f"op-{seed}-{step}",
                logical_step=step,
                invocation_timestamp=f"2026-01-01T00:00:{step:02d}Z",
                completion_timestamp=f"2026-01-01T00:00:{step:02d}Z",
                operation=op,
                request_parameters=params,
                observed_response=resp,
                database_participant=participant,
                attempt_number=1,
                fault_active=fault,
                observed_state_after=snap,
            )
        )
        return resp

    accounts = [("acc-l1-a", "ledger-1"), ("acc-l1-b", "ledger-1"), ("acc-l2-a", "ledger-2")]
    for aid, lid in accounts:
        record(AbstractOperation.CREATE_ACCOUNT, {"account_id": aid, "ledger_id": lid}, lid)
        record(AbstractOperation.FUND_ACCOUNT, {"account_id": aid, "amount_minor": 10_000}, lid)

    # Cross-ledger transfer with duplicate command + crash-after-commit + forward recovery
    tid1 = f"tx-cross-{seed}-1"
    amt = rng.randint(500, 2500)
    record(
        AbstractOperation.START_CROSS_LEDGER_TRANSFER,
        {
            "transfer_id": tid1,
            "source_account_id": "acc-l1-a",
            "destination_account_id": "acc-l2-a",
            "amount_minor": amt,
            "idempotency_key": f"idem-{tid1}",
        },
    )
    record(AbstractOperation.SOURCE_PREPARE, {"transfer_id": tid1, "command_id": f"cmd-sp-{tid1}"}, "ledger-1")
    # Duplicate command delivery
    record(AbstractOperation.SOURCE_PREPARE, {"transfer_id": tid1, "command_id": f"cmd-sp-{tid1}"}, "ledger-1")
    record(AbstractOperation.DESTINATION_PREPARE, {"transfer_id": tid1, "command_id": f"cmd-dp-{tid1}"}, "ledger-2")
    record(AbstractOperation.DECIDE_COMMIT, {"transfer_id": tid1}, "coordinator")
    # Simulated temporary DB unreachability on confirm, then retry
    record(
        AbstractOperation.CONFIRM_SOURCE,
        {"transfer_id": tid1, "command_id": f"cmd-cs-{tid1}"},
        "ledger-1",
        fault="DB_UNREACHABLE",
    )
    record(AbstractOperation.CONFIRM_SOURCE, {"transfer_id": tid1, "command_id": f"cmd-cs-{tid1}"}, "ledger-1")
    record(AbstractOperation.CONFIRM_DESTINATION, {"transfer_id": tid1, "command_id": f"cmd-cd-{tid1}"}, "ledger-2")

    # Cancellation-before-prepare (tombstone)
    tid2 = f"tx-tomb-{seed}-2"
    record(
        AbstractOperation.START_CROSS_LEDGER_TRANSFER,
        {
            "transfer_id": tid2,
            "source_account_id": "acc-l1-a",
            "destination_account_id": "acc-l2-a",
            "amount_minor": 500,
            "idempotency_key": f"idem-{tid2}",
        },
    )
    record(AbstractOperation.DECIDE_CANCEL, {"transfer_id": tid2}, "coordinator")
    record(AbstractOperation.CANCEL_SOURCE, {"transfer_id": tid2, "command_id": f"cmd-xs-{tid2}"}, "ledger-1")
    record(AbstractOperation.SOURCE_PREPARE, {"transfer_id": tid2, "command_id": f"cmd-late-sp-{tid2}"}, "ledger-1")

    # Reversal of settled transfer
    record(AbstractOperation.REVERSE_TRANSFER, {"original_transfer_id": tid1, "reversal_id": f"rev-{tid1}"}, "coordinator")

    return ExecutionHistory(
        history_id=f"hist-{seed}",
        seed=seed,
        events=events,
        final_observed_state=events[-1].observed_state_after,
    )


def test_reference_package_has_no_production_imports() -> None:
    """Reference model must not import production coordinator, worker, participant, or db modules."""
    ref_dir = Path(__file__).parent.parent / "src" / "ledgerguard" / "reference"
    forbidden = (
        "ledgerguard.coordinator",
        "ledgerguard.worker",
        "ledgerguard.participant",
        "ledgerguard.db",
    )
    for py_file in ref_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith(forbidden), f"{py_file} imports {alias.name}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith(forbidden), f"{py_file} imports {node.module}"


def test_seeded_history_reproducibility_and_pass() -> None:
    h1 = _generate_seeded_history(42)
    h2 = _generate_seeded_history(42)
    assert h1.model_dump() == h2.model_dump()

    report = check_history(h1)
    assert report.status == "PASS"
    assert report.divergence is None
    assert "Status:         PASS" in format_report_text(report)


def test_corrupted_decision_flip_detected_at_first_divergence() -> None:
    history = _generate_seeded_history(99)
    # Corrupt intermediate state after DECIDE_COMMIT to flip decision to CANCEL
    for ev in history.events:
        if ev.operation == AbstractOperation.DECIDE_COMMIT and ev.observed_state_after is not None:
            tid = ev.request_parameters["transfer_id"]
            ev.observed_state_after.transfers[tid].decision = "CANCEL"
            corrupt_op_id = ev.operation_id
            break
    else:
        raise AssertionError("DECIDE_COMMIT event not found")

    report = check_history(history)
    assert report.status == "FAIL"
    assert report.divergence is not None
    assert report.divergence.failed_invariant == "I6"
    assert report.divergence.first_divergent_operation_id == corrupt_op_id
    assert len(report.divergence.minimal_relevant_history) >= 1


def test_corrupted_unbalanced_journal_detected() -> None:
    history = _generate_seeded_history(7)
    assert history.final_observed_state is not None
    history.final_observed_state.journal_debit_total_minor["ledger-1"] += 100
    report = check_history(history)
    assert report.status == "FAIL"
    assert report.divergence is not None
    assert report.divergence.failed_invariant == "I1"


def test_incomplete_reachability_never_passes() -> None:
    history = _generate_seeded_history(11)
    assert history.final_observed_state is not None
    history.final_observed_state.reachable_databases = ["coordinator", "ledger-1"]
    report = check_history(history)
    assert report.status == "INCOMPLETE"
    assert report.divergence is not None
    assert report.divergence.failed_invariant == "I14"


def test_cli_check_history_json_and_text(tmp_path: Path) -> None:
    history = _generate_seeded_history(123)
    hist_path = tmp_path / "history.json"
    history.to_json_file(hist_path)

    res_json = subprocess.run(
        [sys.executable, "-m", "ledgerguard.cli", "check-history", str(hist_path), "--format", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res_json.returncode == 0
    payload = json.loads(res_json.stdout)
    assert payload["status"] == "PASS"

    # Corrupt final clearing balance
    assert history.final_observed_state is not None
    history.final_observed_state.clearing_balances["ledger-1"] += 50
    bad_path = tmp_path / "bad_history.json"
    history.to_json_file(bad_path)

    res_bad = subprocess.run(
        [sys.executable, "-m", "ledgerguard.cli", "check-history", str(bad_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert res_bad.returncode == 1
    assert "Status:         FAIL" in res_bad.stdout
    assert "Failed Invariant: I13" in res_bad.stdout


class TCCProtocolStateMachine(RuleBasedStateMachine):
    """Hypothesis stateful machine covering TCC invariants, retries, reordering, tombstones, and reversals."""

    transfers = Bundle("transfers")

    def __init__(self) -> None:
        super().__init__()
        self.model = ReferenceLedgerModel()
        self.l1_accounts = ["l1-a", "l1-b"]
        self.l2_accounts = ["l2-a", "l2-b"]
        for aid in self.l1_accounts:
            self.model.apply(AbstractOperation.CREATE_ACCOUNT, {"account_id": aid, "ledger_id": "ledger-1"})
            self.model.apply(AbstractOperation.FUND_ACCOUNT, {"account_id": aid, "amount_minor": 10_000})
        for aid in self.l2_accounts:
            self.model.apply(AbstractOperation.CREATE_ACCOUNT, {"account_id": aid, "ledger_id": "ledger-2"})
            self.model.apply(AbstractOperation.FUND_ACCOUNT, {"account_id": aid, "amount_minor": 10_000})
        self.tx_counter = 0
        self.initial_total = 40_000

    @rule(target=transfers, amt=st.integers(min_value=100, max_value=3000))
    def start_cross_transfer(self, amt: int) -> str:
        self.tx_counter += 1
        tid = f"tx-{self.tx_counter}"
        self.model.apply(
            AbstractOperation.START_CROSS_LEDGER_TRANSFER,
            {
                "transfer_id": tid,
                "source_account_id": "l1-a",
                "destination_account_id": "l2-a",
                "amount_minor": amt,
                "idempotency_key": f"idem-{tid}",
            },
        )
        return tid

    @rule(tid=transfers, duplicate=st.booleans())
    def source_prepare(self, tid: str, duplicate: bool) -> None:
        cmd = f"sp-{tid}"
        self.model.apply(AbstractOperation.SOURCE_PREPARE, {"transfer_id": tid, "command_id": cmd})
        if duplicate:
            out = self.model.apply(AbstractOperation.SOURCE_PREPARE, {"transfer_id": tid, "command_id": cmd})
            assert out.duplicate_ignored or not out.accepted

    @rule(tid=transfers)
    def destination_prepare(self, tid: str) -> None:
        self.model.apply(AbstractOperation.DESTINATION_PREPARE, {"transfer_id": tid, "command_id": f"dp-{tid}"})

    @rule(tid=transfers)
    def decide_commit(self, tid: str) -> None:
        out = self.model.apply(AbstractOperation.DECIDE_COMMIT, {"transfer_id": tid})
        assert out.invariant_violation is None

    @rule(tid=transfers)
    def decide_cancel(self, tid: str) -> None:
        out = self.model.apply(AbstractOperation.DECIDE_CANCEL, {"transfer_id": tid})
        assert out.invariant_violation is None

    @rule(tid=transfers, fault=st.sampled_from([None, "DB_UNREACHABLE"]))
    def confirm_source(self, tid: str, fault: str | None) -> None:
        self.model.apply(
            AbstractOperation.CONFIRM_SOURCE,
            {"transfer_id": tid, "command_id": f"cs-{tid}"},
            fault_active=fault,
        )

    @rule(tid=transfers)
    def confirm_destination(self, tid: str) -> None:
        self.model.apply(
            AbstractOperation.CONFIRM_DESTINATION,
            {"transfer_id": tid, "command_id": f"cd-{tid}"},
        )

    @rule(tid=transfers)
    def cancel_source(self, tid: str) -> None:
        self.model.apply(
            AbstractOperation.CANCEL_SOURCE,
            {"transfer_id": tid, "command_id": f"xs-{tid}"},
        )

    @rule(tid=transfers)
    def reverse_transfer(self, tid: str) -> None:
        self.model.apply(
            AbstractOperation.REVERSE_TRANSFER,
            {"original_transfer_id": tid, "reversal_id": f"rev-{tid}"},
        )

    @invariant()
    def check_global_invariants(self) -> None:
        # I1: Balanced journals
        for lid in ("ledger-1", "ledger-2"):
            assert self.model.journal_debits[lid] == self.model.journal_credits[lid]
        # I3: Non-negative available balances
        for acc in self.model.accounts.values():
            assert acc.available_balance_minor >= 0
            assert acc.held_amount_minor >= 0
        # I13: Total funds + clearing conservation
        total_posted = sum(acc.posted_balance_minor for acc in self.model.accounts.values())
        assert total_posted - self.model.total_clearing_delta() == self.initial_total


TestTCCStateMachine = pytest.mark.property(TCCProtocolStateMachine.TestCase)
TestTCCStateMachine.settings = hyp_settings(max_examples=40, stateful_step_count=25, deadline=None)
