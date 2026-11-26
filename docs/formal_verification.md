# Formal Verification of the LedgerGuard TCC Protocol (TLA+)

## 1. Scope & Honest Disclaimer

This TLA+ specification models the **abstract state machine** of LedgerGuard's cross-ledger Try-Confirm-Cancel (TCC) transfer protocol (`formal/tla/LedgerGuardTCC.tla`). It proves safety and liveness properties **within the modeled abstraction and finite bounds**. It does **not** constitute a mathematical proof of the entire Python/PL-pgSQL implementation, PostgreSQL internals, or network hardware.

## 2. Abstraction Boundaries

- **Single Transfer Instance:** Models one cross-ledger transfer (`Amount = 4`, `InitSourceBal = 10`, `InitDestBal = 0`) with bounded message loss (`MaxLosses = 1`) and worker crashes (`MaxCrashes = 1`).
- **Concurrent Transfers With Faults:** `formal/tla/LedgerGuardTCCMultiFaults.tla` combines the two other models: three transfers sharing one source and one destination account, re-deliverable per-transfer messages that can be lost (`MaxLosses = 2`), a worker that can crash and restart (`MaxCrashes = 1`), and a recovery action that re-derives missing messages from durable state only. TLC explores 654,840 distinct states and checks `NoOverspend`, conservation, commit/cancel exclusivity, finished-clearing-zero, settled-within-funds, decision monotonicity and termination. Two defective variants must be rejected: `IgnoreHolds = TRUE` (overspend) and `UnsafeRecovery = TRUE` (recovery flips a durable COMMIT into CANCEL, violating `CommitCancelExclusive`). Still bounded: three transfers, at most two losses and one crash, no symmetry reduction, no clock or partition modelling beyond loss.
- **Abstracted Storage:** PostgreSQL ACID transactions, `SELECT ... FOR UPDATE` row locks, and `command_inbox` unique constraints are abstracted as atomic TLA+ actions and the `processedCmds` set.
- **Unbounded Retries Abstracted:** `RetryPending` models the autonomous recovery worker re-emitting missing commands when `workerUp = TRUE`.

## 3. Fairness Assumptions

Liveness properties (`CommittedEventuallySettles`, `CancelledEventuallyReleases`, `EventuallyTerminates`) rely on weak fairness (`WF_vars`) for `WorkerRecover`, `RetryPending`, and participant/coordinator progress actions. Under infinite crash loops or permanent network partitions, liveness cannot hold.

## 4. Traceability Table

| TLA+ Action | Application Event | Implementation Module | Test |
| :--- | :--- | :--- | :--- |
| `SourcePrepare` | `SOURCE_PREPARED` | `src/ledgerguard/participant/workflow_handler.py` (`handle_source_prepare`) | `tests/test_durable_workflow.py` |
| `DestinationPrepare` | `DESTINATION_PREPARED` | `src/ledgerguard/participant/workflow_handler.py` (`handle_destination_prepare`) | `tests/test_durable_workflow.py` |
| `DecideCommit` | `DECISION_COMMIT` | `src/ledgerguard/worker/coordinator_service.py` (`record_durable_decision`) | `tests/test_distributed_failures.py` |
| `DecideCancel` | `DECISION_CANCEL` | `src/ledgerguard/worker/coordinator_service.py` (`record_durable_decision`) | `tests/test_distributed_failures.py` |
| `SourceConfirm` | `SOURCE_CONFIRMED` | `src/ledgerguard/participant/workflow_handler.py` (`handle_source_confirm`) | `tests/test_distributed_failures.py` |
| `DestinationConfirm` | `DESTINATION_CONFIRMED` | `src/ledgerguard/participant/workflow_handler.py` (`handle_destination_confirm`) | `tests/test_distributed_failures.py` |
| `CancelSource` | `TRANSFER_CANCELLED` | `src/ledgerguard/participant/workflow_handler.py` (`handle_participant_cancel`) | `tests/test_distributed_failures.py` |
| `RetryPending` | Forward recovery loop | `src/ledgerguard/worker/orchestrator.py` (`recover_pending_transfers`) | `tests/test_chaos_campaign.py` |
