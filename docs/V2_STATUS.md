# LedgerGuard V2 Status

- **Branch:** `feat/ledgerguard-v2`
- **Branch Base:** `feat/operator-console-redesign` (`16db6617e10e6849fb34d7307a2519564907eaa0`)
- **Starting SHA:** `16db6617e10e6849fb34d7307a2519564907eaa0`
- **Origin/main SHA:** `24319b8006f64c3a84828658709212f9db9cde46`
- **PR #1 (`feat/operator-console-redesign`):** Open (Draft) at `16db6617e10e6849fb34d7307a2519564907eaa0`
- **Current Stage:** Stage 8 — Reversals, refunds and chargebacks (Complete)
- **Next Stage:** Stage 9 — Four-eyes approval and RBAC

## Stage Checklist

- [x] **Stage 0:** Repository and branch preparation
- [x] **Stage 1:** Independent reference model and history checker
- [x] **Stage 2:** Automated chaos campaign engine
- [x] **Stage 3:** TLA+ formal specification
- [x] **Stage 4:** Tamper-evident audit journal
- [x] **Stage 5:** End-to-end OpenTelemetry tracing
- [x] **Stage 6:** Explainable recovery diagnostics
- [x] **Stage 7:** As-of-time balance reconstruction
- [x] **Stage 8:** Reversals, refunds and chargebacks
- [ ] **Stage 9:** Four-eyes approval and RBAC
- [ ] **Stage 10:** Concurrency and performance study
- [ ] **Stage 11:** Adaptive backpressure and circuit breaking
- [ ] **Stage 12:** Disaster recovery and restore verification

## Completed Work

### Stage 0
- Verified clean working tree on `feat/operator-console-redesign` (`16db661`).
- Created `feat/ledgerguard-v2` stacked on `feat/operator-console-redesign`.
- Established `docs/V2_STATUS.md`, `docs/architecture/v2_architecture.md`, `docs/invariants.md`, and machine-readable invariant catalogue (`src/ledgerguard/domain/invariants.py`).
- Executed full baseline verification suite prior to any V2 code changes.

### Stage 1
- Implemented independent, pure-Python reference model (`src/ledgerguard/reference/model.py`) with zero imports from production coordinator, worker, participant, or database modules.
- Defined canonical execution history schema (`src/ledgerguard/reference/history.py`) and step-by-step history checker (`src/ledgerguard/reference/checker.py`) checking intermediate states, decision monotonicity, journal balance, clearing conservation, unresolved holds, and partial reachability.
- Added CLI command `uv run python -m ledgerguard.cli check-history <history-file>` supporting text and JSON output.
- Added Hypothesis stateful tests and divergence detection tests (`tests/test_reference_checker.py`).

### Stage 2
- Implemented deterministic chaos campaign engine (`src/ledgerguard/chaos/models.py`, `src/ledgerguard/chaos/engine.py`) supporting all 18 fault modes, seeded workload/fault scheduling, concurrent workers, forward recovery, stopped-and-drained reconciliation, and `I1`–`I16` invariant matrix reporting.
- Added CLI runner `scripts/run_chaos_campaign.py` and bounded CI chaos campaign step in `.github/workflows/ci.yml`.
- Added production-gated operator API endpoints (`/v1/operator/chaos/run`, `/v1/operator/chaos/campaigns`) and Operator Console Chaos Campaigns view (`apps/console/app/console/chaos/page.tsx`) under grouped navigation (`Observe` / `Operate` / `Verify`).
- Added chaos campaign tests (`tests/test_chaos_campaign.py`) and documentation (`docs/chaos_testing.md`).

### Stage 3
- Created TLA+ formal specification (`formal/tla/LedgerGuardTCC.tla`, `formal/tla/LedgerGuardTCC.cfg`) modeling TCC states (`INIT`..`SETTLED`/`CANCELLED`), durable decisions, command inbox deduplication, cancellation tombstones, worker crash/restart, and bounded message loss.
- Verified 8 safety invariants and 4 temporal/liveness properties under weak fairness via pinned `tla2tools.jar v1.8.0` (`902 states generated, 189 distinct states, depth 10, 0 errors`).
- Added intentionally broken variant (`LedgerGuardTCC_broken.tla`) confirming TLC detects `DecisionMonotonicity` violation (exit 13).
- Added `scripts/run_tla_model_check.sh`, `tla` CI job in `.github/workflows/ci.yml`, and `docs/formal_verification.md` with abstraction boundaries and implementation traceability table.

### Stage 4
- Added forward migrations `migrations/ledger/007_tamper_evident_journal_chain.sql` (transactional SHA-256 hash chain, `journal_chain_head` concurrency lock, `journal_checkpoints`, and backfill) and `migrations/coordinator/005_journal_checkpoint_attestations.sql`.
- Implemented `src/ledgerguard/audit/journal_chain.py` with canonical hash verification, Merkle root computation, coordinator attestation, and CLI commands (`verify-journal-chain`, `create-journal-checkpoint`, `verify-journal-checkpoint`, `verify-all-ledgers`).
- Added `/v1/operator/audit/verify`, `/v1/operator/audit/checkpoint`, Operator Console `/console/audit` view, `scripts/demo_tamper_detection.sh`, `docs/tamper_evident_journal.md`, and `tests/test_tamper_evident_journal.py`.

### Stage 5
- Added OpenTelemetry tracing subsystem (`src/ledgerguard/observability/tracing.py`) supporting `none`, `console`, `otlp`, and `memory` exporters, W3C `traceparent` propagation, coarse `amount_bucket()`, and automatic sensitive-attribute redaction.
- Instrumented HTTP middleware, coordinator transfer submission, idempotency lookup, outbox enqueue, participant `source_prepare`, forward recovery (`recovery.retry_transfer`), and cross-ledger reconciliation.
- Added `/v1/operator/traces`, `/v1/operator/transfers/{transfer_id}/trace`, Operator Console `/console/traces` view, optional `jaeger` Compose profile, `docs/observability.md`, and `tests/test_tracing.py`.

### Stage 6
- Implemented deterministic rule-based recovery diagnostic engine (`src/ledgerguard/recovery_explain/engine.py`) covering all TCC states, partial reachability, crash-after-commit, cancellation tombstones, contradictory states, and `UNCLASSIFIED_STATE` fallback.
- Added `/v1/operator/transfers/{transfer_id}/explain`, `/v1/operator/recovery/queue`, Operator Console `/console/recovery` view under **Operate**, `docs/recovery_explanations.md`, and `tests/test_recovery_explain.py`.

### Stage 7
- Added forward migration `migrations/ledger/008_balance_snapshots.sql` for immutable, SHA-256 checksummed `balance_snapshots`.
- Implemented `src/ledgerguard/history/reconstruction.py` with snapshot creation, deterministic sequence-ordered replay, snapshot checksum verification + fallback, pre-creation timestamp rejection, and clearing balance reconstruction.
- Added `/v1/operator/history/accounts/{account_id}/balance`, `/snapshot`, `/clearing`, Operator Console `/console/history`, `docs/historical_reconstruction.md`, and `tests/test_history_reconstruction.py`.

### Stage 8
- Added forward migration `migrations/coordinator/006_refunds_and_disputes.sql` (`transfer_refunds`, `disputes`, immutable `dispute_events` trigger, `transfers.refunded_amount_minor`).
- Implemented `src/ledgerguard/disputes/service.py` supporting idempotent partial/full refunds with row-locked cumulative limit enforcement and the 8-state chargeback dispute lifecycle.
- Added `/v1/operator/transfers/{transfer_id}/refund`, `/v1/operator/disputes`, `/v1/operator/disputes/{dispute_id}/transition`, Operator Console `/console/disputes`, `docs/reversals_refunds_chargebacks.md`, and `tests/test_disputes_refunds.py`.

## Baseline Verification Evidence

- `uv run ruff check .`: Passed (0 errors)
- `uv run mypy src`: Passed (0 issues in 35 source files)
- `uv run pytest -ra -W error`: 74 passed in 20.54s
- `./scripts/demo_signature_recovery.sh`: Passed (8/8 steps, 0 findings)
- `apps/console` `npm run lint`: Passed (0 errors)
- `apps/console` `npm test`: 45 passed across 18 suites
- `apps/console` `npm run build`: Compiled successfully (13 static/dynamic routes)
- `python3 scripts/security_audit_scanner.py`: SCAN PASSED

## Known Limitations (Baseline)

- Cross-ledger transfers use application-level TCC with forward recovery; there is no global cross-database snapshot isolation.
- V1 relies on existing `tests/test_reference_model.py` without an independent standalone history checker CLI or chaos campaign engine (addressed in Stages 1–2).
- No formal TLA+ model, journal hash chaining, distributed tracing, or dual-control approvals exist yet (addressed in Stages 3–12).
