"""Pure, deterministic reference model for LedgerGuard distributed transfers.

No imports from coordinator, worker, participant, or database modules.
All monetary values are integer paise.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class AbstractOperation(StrEnum):
    """Abstract operations supported by the independent reference model."""

    CREATE_ACCOUNT = "create_account"
    FUND_ACCOUNT = "fund_account"
    LOCAL_TRANSFER = "local_transfer"
    START_CROSS_LEDGER_TRANSFER = "start_cross_ledger_transfer"
    SOURCE_PREPARE = "source_prepare"
    DESTINATION_PREPARE = "destination_prepare"
    DECIDE_COMMIT = "decide_commit"
    DECIDE_CANCEL = "decide_cancel"
    CONFIRM_SOURCE = "confirm_source"
    CONFIRM_DESTINATION = "confirm_destination"
    CANCEL_SOURCE = "cancel_source"
    CANCEL_DESTINATION = "cancel_destination"
    RETRY_COMMAND = "retry_command"
    REVERSE_TRANSFER = "reverse_transfer"


@dataclass
class ReferenceAccount:
    """In-memory account state."""

    account_id: str
    ledger_id: str
    posted_balance_minor: int = 0
    held_amount_minor: int = 0
    status: str = "ACTIVE"

    @property
    def available_balance_minor(self) -> int:
        return self.posted_balance_minor - self.held_amount_minor


@dataclass
class ReferenceTransfer:
    """In-memory transfer and TCC protocol state."""

    transfer_id: str
    source_account_id: str
    destination_account_id: str
    source_ledger_id: str
    destination_ledger_id: str
    amount_minor: int
    is_cross_ledger: bool
    idempotency_key: str | None = None
    state: str = "ACCEPTED"  # ACCEPTED, PREPARING, COMMITTING, CANCELLING, SETTLED, CANCELLED, REVERSED
    decision: str | None = None  # COMMIT or CANCEL
    source_prepared: bool = False
    destination_prepared: bool = False
    source_confirmed: bool = False
    destination_confirmed: bool = False
    source_cancelled: bool = False
    destination_cancelled: bool = False
    reversed: bool = False


@dataclass
class OperationOutcome:
    """Deterministic result of applying an abstract operation."""

    accepted: bool
    status: str
    error_code: str | None = None
    duplicate_ignored: bool = False
    invariant_violation: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReferenceLedgerModel:
    """Independent deterministic state machine for LedgerGuard."""

    accounts: dict[str, ReferenceAccount] = field(default_factory=dict)
    transfers: dict[str, ReferenceTransfer] = field(default_factory=dict)
    active_holds: dict[str, tuple[str, int]] = field(default_factory=dict)  # transfer_id -> (account_id, amount)
    source_tombstones: set[str] = field(default_factory=set)
    destination_tombstones: set[str] = field(default_factory=set)
    clearing_balances: dict[str, int] = field(default_factory=lambda: {"ledger-1": 0, "ledger-2": 0})
    journal_debits: dict[str, int] = field(default_factory=lambda: {"ledger-1": 0, "ledger-2": 0})
    journal_credits: dict[str, int] = field(default_factory=lambda: {"ledger-1": 0, "ledger-2": 0})
    idempotency_results: dict[str, tuple[str, OperationOutcome]] = field(default_factory=dict)
    command_inbox: dict[str, OperationOutcome] = field(default_factory=dict)
    command_history: dict[str, tuple[str, dict[str, Any]]] = field(default_factory=dict)
    reversals: dict[str, str] = field(default_factory=dict)  # original_transfer_id -> reversal_id

    def _validate_int_amount(self, amount: Any) -> int | None:
        if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
            return None
        return amount

    def apply(
        self,
        operation: str,
        params: dict[str, Any],
        *,
        fault_active: str | None = None,
    ) -> OperationOutcome:
        """Apply one abstract operation deterministically."""
        if fault_active == "DB_UNREACHABLE":
            return OperationOutcome(
                accepted=False,
                status="UNAVAILABLE",
                error_code="DB_UNREACHABLE",
            )

        if operation == AbstractOperation.RETRY_COMMAND:
            cmd_id = params.get("command_id")
            if cmd_id and cmd_id in self.command_history:
                orig_op, orig_params = self.command_history[cmd_id]
                return self.apply(orig_op, orig_params, fault_active=fault_active)
            return OperationOutcome(accepted=False, status="REJECTED", error_code="UNKNOWN_COMMAND")

        command_id = params.get("command_id")
        if command_id and command_id in self.command_inbox:
            prev = self.command_inbox[command_id]
            return OperationOutcome(
                accepted=prev.accepted,
                status=prev.status,
                error_code=prev.error_code,
                duplicate_ignored=True,
                details=dict(prev.details),
            )

        if command_id:
            self.command_history[command_id] = (operation, dict(params))

        outcome = self._dispatch(operation, params)

        if command_id and outcome.status != "UNAVAILABLE":
            self.command_inbox[command_id] = outcome

        return outcome

    def _dispatch(self, operation: str, params: dict[str, Any]) -> OperationOutcome:
        handlers = {
            AbstractOperation.CREATE_ACCOUNT: self._op_create_account,
            AbstractOperation.FUND_ACCOUNT: self._op_fund_account,
            AbstractOperation.LOCAL_TRANSFER: self._op_local_transfer,
            AbstractOperation.START_CROSS_LEDGER_TRANSFER: self._op_start_cross_ledger,
            AbstractOperation.SOURCE_PREPARE: self._op_source_prepare,
            AbstractOperation.DESTINATION_PREPARE: self._op_destination_prepare,
            AbstractOperation.DECIDE_COMMIT: self._op_decide_commit,
            AbstractOperation.DECIDE_CANCEL: self._op_decide_cancel,
            AbstractOperation.CONFIRM_SOURCE: self._op_confirm_source,
            AbstractOperation.CONFIRM_DESTINATION: self._op_confirm_destination,
            AbstractOperation.CANCEL_SOURCE: self._op_cancel_source,
            AbstractOperation.CANCEL_DESTINATION: self._op_cancel_destination,
            AbstractOperation.REVERSE_TRANSFER: self._op_reverse_transfer,
        }
        handler = handlers.get(AbstractOperation(operation))
        if handler is None:
            return OperationOutcome(accepted=False, status="REJECTED", error_code="UNSUPPORTED_OP")
        return handler(params)

    def _op_create_account(self, params: dict[str, Any]) -> OperationOutcome:
        acct_id = str(params["account_id"])
        ledger_id = str(params["ledger_id"])
        if acct_id in self.accounts:
            return OperationOutcome(accepted=True, status="EXISTS", duplicate_ignored=True)
        self.accounts[acct_id] = ReferenceAccount(account_id=acct_id, ledger_id=ledger_id)
        self.clearing_balances.setdefault(ledger_id, 0)
        self.journal_debits.setdefault(ledger_id, 0)
        self.journal_credits.setdefault(ledger_id, 0)
        return OperationOutcome(accepted=True, status="CREATED")

    def _op_fund_account(self, params: dict[str, Any]) -> OperationOutcome:
        acct_id = str(params["account_id"])
        amount = self._validate_int_amount(params.get("amount_minor"))
        if amount is None:
            return OperationOutcome(accepted=False, status="REJECTED", error_code="INVALID_AMOUNT")
        acct = self.accounts.get(acct_id)
        if acct is None or acct.status != "ACTIVE":
            return OperationOutcome(accepted=False, status="REJECTED", error_code="ACCOUNT_NOT_ACTIVE")
        acct.posted_balance_minor += amount
        self.journal_debits[acct.ledger_id] += amount
        self.journal_credits[acct.ledger_id] += amount
        return OperationOutcome(accepted=True, status="FUNDED")

    def _op_local_transfer(self, params: dict[str, Any]) -> OperationOutcome:
        idem_key = params.get("idempotency_key")
        payload_sig = f"{params.get('source_account_id')}:{params.get('destination_account_id')}:{params.get('amount_minor')}"
        if idem_key and idem_key in self.idempotency_results:
            saved_sig, saved_out = self.idempotency_results[idem_key]
            if saved_sig != payload_sig:
                return OperationOutcome(accepted=False, status="CONFLICT", error_code="IDEMPOTENCY_CONFLICT")
            return OperationOutcome(
                accepted=saved_out.accepted,
                status=saved_out.status,
                error_code=saved_out.error_code,
                duplicate_ignored=True,
                details=dict(saved_out.details),
            )

        transfer_id = str(params["transfer_id"])
        src_id = str(params["source_account_id"])
        dst_id = str(params["destination_account_id"])
        amount = self._validate_int_amount(params.get("amount_minor"))
        if amount is None or src_id == dst_id:
            out = OperationOutcome(accepted=False, status="REJECTED", error_code="INVALID_TRANSFER")
            if idem_key:
                self.idempotency_results[idem_key] = (payload_sig, out)
            return out

        src = self.accounts.get(src_id)
        dst = self.accounts.get(dst_id)
        if src is None or dst is None or src.ledger_id != dst.ledger_id:
            out = OperationOutcome(accepted=False, status="REJECTED", error_code="INVALID_LEDGER")
            if idem_key:
                self.idempotency_results[idem_key] = (payload_sig, out)
            return out

        if src.status != "ACTIVE" or dst.status != "ACTIVE" or src.available_balance_minor < amount:
            out = OperationOutcome(accepted=False, status="REJECTED", error_code="INSUFFICIENT_OR_INACTIVE")
            if idem_key:
                self.idempotency_results[idem_key] = (payload_sig, out)
            return out

        src.posted_balance_minor -= amount
        dst.posted_balance_minor += amount
        self.journal_debits[src.ledger_id] += amount
        self.journal_credits[src.ledger_id] += amount
        self.transfers[transfer_id] = ReferenceTransfer(
            transfer_id=transfer_id,
            source_account_id=src_id,
            destination_account_id=dst_id,
            source_ledger_id=src.ledger_id,
            destination_ledger_id=dst.ledger_id,
            amount_minor=amount,
            is_cross_ledger=False,
            idempotency_key=idem_key,
            state="SETTLED",
            decision="COMMIT",
            source_prepared=True,
            destination_prepared=True,
            source_confirmed=True,
            destination_confirmed=True,
        )
        out = OperationOutcome(accepted=True, status="SETTLED", details={"transfer_id": transfer_id})
        if idem_key:
            self.idempotency_results[idem_key] = (payload_sig, out)
        return out

    def _op_start_cross_ledger(self, params: dict[str, Any]) -> OperationOutcome:
        idem_key = params.get("idempotency_key")
        payload_sig = f"{params.get('source_account_id')}:{params.get('destination_account_id')}:{params.get('amount_minor')}"
        if idem_key and idem_key in self.idempotency_results:
            saved_sig, saved_out = self.idempotency_results[idem_key]
            if saved_sig != payload_sig:
                return OperationOutcome(accepted=False, status="CONFLICT", error_code="IDEMPOTENCY_CONFLICT")
            return OperationOutcome(
                accepted=saved_out.accepted,
                status=saved_out.status,
                error_code=saved_out.error_code,
                duplicate_ignored=True,
                details=dict(saved_out.details),
            )

        transfer_id = str(params["transfer_id"])
        src_id = str(params["source_account_id"])
        dst_id = str(params["destination_account_id"])
        amount = self._validate_int_amount(params.get("amount_minor"))
        src = self.accounts.get(src_id)
        dst = self.accounts.get(dst_id)
        if amount is None or src is None or dst is None or src.ledger_id == dst.ledger_id:
            out = OperationOutcome(accepted=False, status="REJECTED", error_code="INVALID_CROSS_LEDGER")
            if idem_key:
                self.idempotency_results[idem_key] = (payload_sig, out)
            return out

        self.transfers[transfer_id] = ReferenceTransfer(
            transfer_id=transfer_id,
            source_account_id=src_id,
            destination_account_id=dst_id,
            source_ledger_id=src.ledger_id,
            destination_ledger_id=dst.ledger_id,
            amount_minor=amount,
            is_cross_ledger=True,
            idempotency_key=idem_key,
            state="PREPARING",
        )
        out = OperationOutcome(accepted=True, status="PREPARING", details={"transfer_id": transfer_id})
        if idem_key:
            self.idempotency_results[idem_key] = (payload_sig, out)
        return out

    def _op_source_prepare(self, params: dict[str, Any]) -> OperationOutcome:
        tid = str(params["transfer_id"])
        tx = self.transfers.get(tid)
        if tx is None:
            return OperationOutcome(accepted=False, status="REJECTED", error_code="UNKNOWN_TRANSFER")
        if tid in self.source_tombstones:
            return OperationOutcome(accepted=False, status="REJECTED", error_code="TOMBSTONE_EXISTS")
        if tx.source_prepared:
            return OperationOutcome(accepted=True, status="PREPARED", duplicate_ignored=True)
        src = self.accounts[tx.source_account_id]
        if src.status != "ACTIVE" or src.available_balance_minor < tx.amount_minor:
            return OperationOutcome(accepted=False, status="REJECTED", error_code="INSUFFICIENT_FUNDS")
        src.held_amount_minor += tx.amount_minor
        self.active_holds[tid] = (src.account_id, tx.amount_minor)
        tx.source_prepared = True
        return OperationOutcome(accepted=True, status="PREPARED")

    def _op_destination_prepare(self, params: dict[str, Any]) -> OperationOutcome:
        tid = str(params["transfer_id"])
        tx = self.transfers.get(tid)
        if tx is None:
            return OperationOutcome(accepted=False, status="REJECTED", error_code="UNKNOWN_TRANSFER")
        if tid in self.destination_tombstones:
            return OperationOutcome(accepted=False, status="REJECTED", error_code="TOMBSTONE_EXISTS")
        if tx.destination_prepared:
            return OperationOutcome(accepted=True, status="PREPARED", duplicate_ignored=True)
        dst = self.accounts[tx.destination_account_id]
        if dst.status != "ACTIVE":
            return OperationOutcome(accepted=False, status="REJECTED", error_code="DESTINATION_NOT_ACTIVE")
        tx.destination_prepared = True
        return OperationOutcome(accepted=True, status="PREPARED")

    def _op_decide_commit(self, params: dict[str, Any]) -> OperationOutcome:
        tid = str(params["transfer_id"])
        tx = self.transfers.get(tid)
        if tx is None:
            return OperationOutcome(accepted=False, status="REJECTED", error_code="UNKNOWN_TRANSFER")
        if tx.decision == "CANCEL":
            return OperationOutcome(
                accepted=False,
                status="REJECTED",
                error_code="DECISION_CONFLICT",
            )
        if tx.decision == "COMMIT":
            return OperationOutcome(accepted=True, status="COMMITTING", duplicate_ignored=True)
        if not (tx.source_prepared and tx.destination_prepared):
            return OperationOutcome(accepted=False, status="REJECTED", error_code="NOT_PREPARED")
        tx.decision = "COMMIT"
        tx.state = "COMMITTING"
        return OperationOutcome(accepted=True, status="COMMITTING")

    def _op_decide_cancel(self, params: dict[str, Any]) -> OperationOutcome:
        tid = str(params["transfer_id"])
        tx = self.transfers.get(tid)
        if tx is None:
            return OperationOutcome(accepted=False, status="REJECTED", error_code="UNKNOWN_TRANSFER")
        if tx.decision == "COMMIT":
            return OperationOutcome(
                accepted=False,
                status="REJECTED",
                error_code="DECISION_CONFLICT",
            )
        if tx.decision == "CANCEL":
            return OperationOutcome(accepted=True, status="CANCELLING", duplicate_ignored=True)
        tx.decision = "CANCEL"
        tx.state = "CANCELLING"
        return OperationOutcome(accepted=True, status="CANCELLING")

    def _op_confirm_source(self, params: dict[str, Any]) -> OperationOutcome:
        tid = str(params["transfer_id"])
        tx = self.transfers.get(tid)
        if tx is None:
            return OperationOutcome(accepted=False, status="REJECTED", error_code="UNKNOWN_TRANSFER")
        if tx.decision != "COMMIT":
            return OperationOutcome(
                accepted=False,
                status="REJECTED",
                error_code="NO_COMMIT_DECISION",
            )
        if tx.source_confirmed:
            return OperationOutcome(accepted=True, status="CONFIRMED", duplicate_ignored=True)
        src = self.accounts[tx.source_account_id]
        hold = self.active_holds.pop(tid, None)
        if hold is not None:
            src.held_amount_minor -= hold[1]
        src.posted_balance_minor -= tx.amount_minor
        self.clearing_balances[tx.source_ledger_id] -= tx.amount_minor
        self.journal_debits[tx.source_ledger_id] += tx.amount_minor
        self.journal_credits[tx.source_ledger_id] += tx.amount_minor
        tx.source_confirmed = True
        if tx.destination_confirmed:
            tx.state = "SETTLED"
        return OperationOutcome(accepted=True, status="CONFIRMED")

    def _op_confirm_destination(self, params: dict[str, Any]) -> OperationOutcome:
        tid = str(params["transfer_id"])
        tx = self.transfers.get(tid)
        if tx is None:
            return OperationOutcome(accepted=False, status="REJECTED", error_code="UNKNOWN_TRANSFER")
        if tx.decision != "COMMIT":
            return OperationOutcome(
                accepted=False,
                status="REJECTED",
                error_code="NO_COMMIT_DECISION",
            )
        if tx.destination_confirmed:
            return OperationOutcome(accepted=True, status="CONFIRMED", duplicate_ignored=True)
        dst = self.accounts[tx.destination_account_id]
        dst.posted_balance_minor += tx.amount_minor
        self.clearing_balances[tx.destination_ledger_id] += tx.amount_minor
        self.journal_debits[tx.destination_ledger_id] += tx.amount_minor
        self.journal_credits[tx.destination_ledger_id] += tx.amount_minor
        tx.destination_confirmed = True
        if tx.source_confirmed:
            tx.state = "SETTLED"
        return OperationOutcome(accepted=True, status="CONFIRMED")

    def _op_cancel_source(self, params: dict[str, Any]) -> OperationOutcome:
        tid = str(params["transfer_id"])
        tx = self.transfers.get(tid)
        if tx is not None and tx.decision == "COMMIT":
            return OperationOutcome(
                accepted=False,
                status="REJECTED",
                error_code="CANNOT_CANCEL_COMMITTED",
            )
        self.source_tombstones.add(tid)
        hold = self.active_holds.pop(tid, None)
        if hold is not None:
            acct_id, amt = hold
            self.accounts[acct_id].held_amount_minor -= amt
        if tx is not None:
            tx.source_cancelled = True
            if tx.destination_cancelled or not tx.destination_prepared:
                tx.state = "CANCELLED"
        return OperationOutcome(accepted=True, status="CANCELLED")

    def _op_cancel_destination(self, params: dict[str, Any]) -> OperationOutcome:
        tid = str(params["transfer_id"])
        tx = self.transfers.get(tid)
        if tx is not None and tx.decision == "COMMIT":
            return OperationOutcome(
                accepted=False,
                status="REJECTED",
                error_code="CANNOT_CANCEL_COMMITTED",
            )
        self.destination_tombstones.add(tid)
        if tx is not None:
            tx.destination_cancelled = True
            if tx.source_cancelled or not tx.source_prepared:
                tx.state = "CANCELLED"
        return OperationOutcome(accepted=True, status="CANCELLED")

    def _op_reverse_transfer(self, params: dict[str, Any]) -> OperationOutcome:
        orig_id = str(params["original_transfer_id"])
        rev_id = str(params.get("reversal_id", f"rev-{orig_id}"))
        tx = self.transfers.get(orig_id)
        if tx is None or tx.state != "SETTLED":
            return OperationOutcome(accepted=False, status="REJECTED", error_code="NOT_SETTLED")
        if orig_id in self.reversals:
            return OperationOutcome(accepted=True, status="REVERSED", duplicate_ignored=True)
        src = self.accounts[tx.source_account_id]
        dst = self.accounts[tx.destination_account_id]
        if dst.available_balance_minor < tx.amount_minor:
            return OperationOutcome(accepted=False, status="REJECTED", error_code="INSUFFICIENT_REVERSAL_FUNDS")
        dst.posted_balance_minor -= tx.amount_minor
        src.posted_balance_minor += tx.amount_minor
        if tx.is_cross_ledger:
            self.clearing_balances[tx.destination_ledger_id] -= tx.amount_minor
            self.clearing_balances[tx.source_ledger_id] += tx.amount_minor
            self.journal_debits[tx.destination_ledger_id] += tx.amount_minor
            self.journal_credits[tx.destination_ledger_id] += tx.amount_minor
            self.journal_debits[tx.source_ledger_id] += tx.amount_minor
            self.journal_credits[tx.source_ledger_id] += tx.amount_minor
        else:
            self.journal_debits[tx.source_ledger_id] += tx.amount_minor
            self.journal_credits[tx.source_ledger_id] += tx.amount_minor
        tx.reversed = True
        tx.state = "REVERSED"
        self.reversals[orig_id] = rev_id
        return OperationOutcome(accepted=True, status="REVERSED", details={"reversal_id": rev_id})

    def total_clearing_delta(self) -> int:
        return sum(self.clearing_balances.values())

    def unresolved_holds_for_ledger(self, ledger_id: str) -> int:
        return sum(
            1
            for acct_id, _ in self.active_holds.values()
            if self.accounts[acct_id].ledger_id == ledger_id
        )
