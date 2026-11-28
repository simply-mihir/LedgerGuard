"""Head-to-head comparison of TCC (LedgerGuard), XA two-phase commit, and Sagas."""

from ledgerguard.comparison.protocols import (
    Outcome,
    SagaProtocol,
    TccProtocol,
    TransferProtocol,
    XaProtocol,
    XaUnavailableError,
    all_protocols,
)
from ledgerguard.comparison.scenarios import (
    ComparisonConfig,
    ComparisonReport,
    run_comparison,
)

__all__ = [
    "ComparisonConfig",
    "ComparisonReport",
    "Outcome",
    "SagaProtocol",
    "TccProtocol",
    "TransferProtocol",
    "XaProtocol",
    "XaUnavailableError",
    "all_protocols",
    "run_comparison",
]
