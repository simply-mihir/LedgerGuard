"""Canonical execution history event format for LedgerGuard verification."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class AccountSnapshot(BaseModel):
    """Observed state of a single account on a participant ledger."""

    account_id: str
    ledger_id: str
    posted_balance_minor: int
    held_amount_minor: int
    available_balance_minor: int
    status: str = "ACTIVE"


class TransferSnapshot(BaseModel):
    """Observed state of a transfer at the coordinator."""

    transfer_id: str
    state: str
    decision: str | None = None
    source_confirmed: bool = False
    destination_confirmed: bool = False
    amount_minor: int = 0
    reversed: bool = False


class ObservedClusterState(BaseModel):
    """Observed state across Coordinator, Ledger 1, and Ledger 2."""

    reachable_databases: list[str] = Field(
        default_factory=lambda: ["coordinator", "ledger-1", "ledger-2"]
    )
    accounts: dict[str, AccountSnapshot] = Field(default_factory=dict)
    transfers: dict[str, TransferSnapshot] = Field(default_factory=dict)
    clearing_balances: dict[str, int] = Field(
        default_factory=lambda: {"ledger-1": 0, "ledger-2": 0}
    )
    journal_debit_total_minor: dict[str, int] = Field(
        default_factory=lambda: {"ledger-1": 0, "ledger-2": 0}
    )
    journal_credit_total_minor: dict[str, int] = Field(
        default_factory=lambda: {"ledger-1": 0, "ledger-2": 0}
    )
    unresolved_holds_count: dict[str, int] = Field(
        default_factory=lambda: {"ledger-1": 0, "ledger-2": 0}
    )


class HistoryEvent(BaseModel):
    """Canonical single operation record in an execution history."""

    operation_id: str
    logical_step: int
    invocation_timestamp: str
    completion_timestamp: str
    operation: str
    request_parameters: dict[str, Any] = Field(default_factory=dict)
    observed_response: dict[str, Any] = Field(default_factory=dict)
    database_participant: str = "coordinator"
    attempt_number: int = 1
    trace_id: str | None = None
    fault_active: str | None = None
    error_category: str | None = None
    observed_state_after: ObservedClusterState | None = None


class ExecutionHistory(BaseModel):
    """Canonical, seed-reproducible execution history for offline checking."""

    history_id: str
    seed: int
    metadata: dict[str, Any] = Field(default_factory=dict)
    events: list[HistoryEvent] = Field(default_factory=list)
    final_observed_state: ObservedClusterState | None = None

    @classmethod
    def from_json_file(cls, path: str | Path) -> ExecutionHistory:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.model_validate(data)

    def to_json_file(self, path: str | Path) -> None:
        Path(path).write_text(self.model_dump_json(indent=2), encoding="utf-8")
