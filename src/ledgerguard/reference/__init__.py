"""Independent reference model and canonical history checker for LedgerGuard.

This package is intentionally isolated from production coordinator, worker,
participant, and database modules so it can serve as an independent oracle.
"""

from ledgerguard.reference.checker import (
    CheckReport,
    DivergenceDetail,
    HistoryChecker,
    check_history,
    format_report_text,
)
from ledgerguard.reference.history import (
    AccountSnapshot,
    ExecutionHistory,
    HistoryEvent,
    ObservedClusterState,
    TransferSnapshot,
)
from ledgerguard.reference.model import (
    AbstractOperation,
    OperationOutcome,
    ReferenceAccount,
    ReferenceLedgerModel,
    ReferenceTransfer,
)

__all__ = [
    "AbstractOperation",
    "AccountSnapshot",
    "CheckReport",
    "DivergenceDetail",
    "ExecutionHistory",
    "HistoryChecker",
    "HistoryEvent",
    "ObservedClusterState",
    "OperationOutcome",
    "ReferenceAccount",
    "ReferenceLedgerModel",
    "ReferenceTransfer",
    "TransferSnapshot",
    "check_history",
    "format_report_text",
]
