# Adaptive Backpressure & Circuit Breaking

## Overview

LedgerGuard V2 protects participant ledgers from overload and retry storms using a durable, PostgreSQL-backed per-participant circuit breaker (`CLOSED`, `OPEN`, `HALF_OPEN`) and admission controller (`src/ledgerguard/resilience/circuit_breaker.py`).

## Invariant Guarantees

- **Durable Obligations Protected:** Opening a circuit blocks *new* transfer admissions (`BackpressureRejectedError`) but **never** cancels or blocks forward recovery of already-committed transfers.
- **Restart Persistence:** Circuit states and audit transitions are persisted in `participant_resilience_state` and `resilience_audit_events`.
- **Recovery Hysteresis:** `OPEN` transitions to `HALF_OPEN` after cooldown, and requires `recovery_success_threshold` consecutive successes to return to `CLOSED`.
