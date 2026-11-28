# LedgerGuard V2 Architecture Specification

## 1. Purpose and Scope

LedgerGuard V2 extends the V1 three-database financial ledger (`coordinator_db`, `ledger1_db`, `ledger2_db`) into an evidence-driven, formally modeled, and chaos-tested distributed ledger system. V2 preserves the V1 3-database PostgreSQL 17 topology, integer-paise double-entry accounting kernel, and application-level Try-Confirm-Cancel (TCC) forward-recovery protocol while adding formal verification, tamper-evident journals, observability, explainable diagnostics, historical reconstruction, dispute workflows, dual-control RBAC, performance benchmarking, adaptive backpressure, and disaster-recovery verification.

## 2. Components

1. **Coordinator Domain (`coordinator_db`, port 5442):**
   - `DirectoryService`: Customer onboarding and account-to-ledger routing.
   - `TransferCoordinator` & `Orchestrator`: Application-level TCC coordinator, durable `transfer_decisions`, transactional outbox, and autonomous forward recovery.
   - `ReconciliationEngine`: Cross-database reachability probing and zero-sum clearing conservation checks.
   - **V2 Additions:** Journal checkpoint attestation store, dispute/chargeback workflow state, four-eyes approval requests & immutable audit log, per-participant circuit-breaker & backpressure state.

2. **Participant Ledger Domains (`ledger1_db` port 5443, `ledger2_db` port 5444):**
   - Double-entry accounting kernel (`journal_headers`, `journal_lines`, `account_balances`, `post_journal` PL/pgSQL).
   - TCC participant tables (`holds`, `transfer_intents`, `command_inbox`, `participant_outbox`).
   - **V2 Additions:** Tamper-evident SHA-256 hash chain on `journal_headers`, Merkle checkpoints, immutable balance snapshots for as-of-time reconstruction, compensating reversal/refund/chargeback postings.

3. **Verification & Diagnostic Subsystems (Python `src/ledgerguard/`):**
   - `reference/`: Independent pure-Python reference model and canonical history checker (no imports from production coordinator/worker).
   - `chaos/`: Deterministic fault-injection campaign engine running against isolated Docker Compose stacks.
   - `formal/tla/`: TLA+ specification (`LedgerGuardTCC.tla`) and TLC model-checking configurations.
   - `recovery_explain/`: Deterministic rule-based diagnostic engine for unresolved transfers.
   - `observability/`: OpenTelemetry tracing with context propagation across HTTP, outbox, inbox, and recovery.
   - `resilience/`: Per-participant circuit breakers (`CLOSED`, `OPEN`, `HALF_OPEN`) and adaptive admission control.

4. **Operator Console (`apps/console/`, Next.js 15):**
   - Preserves the rounded glassmorphic design system and reduced-motion accessibility.
   - Grouped navigation: **Observe** (Overview, Accounts, Transfers, Traces, Reconciliation), **Operate** (Recovery, Approvals, Disputes, Resilience), **Verify** (Chaos, Formal Model, Audit Integrity, Performance, Disaster Recovery).

## 3. Protocol Boundaries

- **Locally Atomic Participant Transactions:** Every `source_prepare`, `destination_prepare`, `source_confirm`, `destination_confirm`, and `cancel` executes as a short, locally committed PostgreSQL transaction. No XA 2PC or `PREPARE TRANSACTION` is used.
- **Irreversible Decision Boundary:** Once `COMMIT` is durably persisted in `transfer_decisions`, forward recovery must settle the transfer; unilateral rollback is forbidden.
- **Trust & Role Boundaries:**
  - `ledgerguard_admin`: Migration owner; owns schemas, triggers, and `SECURITY DEFINER` functions.
  - `ledgerguard_app`: Runtime role; cannot directly `UPDATE`/`DELETE` journals or alter hash chains.
  - `ledgerguard_reporter`: Read-only reconciliation/audit role; strictly denied access to authentication tables (`operators`, `operator_sessions`, `operator_login_attempts`).

## 4. Invariants

All 16 core invariants (`I1`–`I16`) are catalogued in [`docs/invariants.md`](../invariants.md) and encoded in machine-readable form in `src/ledgerguard/domain/invariants.py`. Every stage must preserve all invariants without relaxation.

## 5. Evidence Strategy

Every claim in LedgerGuard V2 is backed by reproducible artifacts:
- **Property-Based & Reference Checking:** Hypothesis stateful tests + independent history checker comparing coordinator/participant logs against the reference model.
- **Formal Modeling:** Bounded TLC safety and liveness checks in CI, plus documented abstraction boundaries.
- **Chaos Campaigns:** Seeded, deterministic fault-injection campaigns with isolated PostgreSQL volumes.
- **Cryptographic Integrity:** Canonical SHA-256 journal hash chains + Merkle checkpoints attested in the coordinator trust boundary.
- **Performance & DR:** Raw CSV/JSON telemetry with fixed seeds, warmup/measured windows, and isolated restore drills measuring actual RPO/RTO.

## 6. Threat Model Summary

- **Privileged / Offline DB Tampering:** Detected via canonical SHA-256 hash chains and cross-boundary Merkle checkpoints (Stage 4).
- **Insider / Single-Operator Abuse:** Mitigated via four-eyes dual control, immutable payload hashing, and recent-auth MFA checks (Stage 9).
- **Auth & Session Compromise:** Mitigated via Argon2id, RFC 6238 TOTP with replay protection, SHA-256 session token digests, HttpOnly/SameSite/Secure cookies, CSRF tokens, and reporter-role isolation.
- **Unsafe Lab Endpoints in Production:** Chaos, tamper-fixture, and disaster-recovery endpoints/scripts are gated behind explicit non-production flags and environment guards.

## 7. Feature Flags

- `LEDGERGUARD_ENV`: Environment mode (`local`, `test`, `ci`, `production`).
- `LEDGERGUARD_ENABLE_LAB_ENDPOINTS`: `false` by default in production; gates chaos/tamper/failpoint controls.
- `LEDGERGUARD_OTEL_EXPORTER`: `none` | `console` | `otlp` | `memory` (for tests).
- `LEDGERGUARD_LLM_REWRITE_ENABLED`: `false` by default; optional phrasing layer strictly decoupled from deterministic recovery rules.

## 8. Migration Policy

- All schema changes use forward-only numbered SQL migrations in `migrations/coordinator/` and `migrations/ledger/`.
- Existing migrations (`coordinator/001..004`, `ledger/001..006`) are never modified retroactively.
- Every migration must apply cleanly from empty PostgreSQL 17 databases and preserve `ledgerguard_app` and `ledgerguard_reporter` least-privilege boundaries.
