# LedgerGuard V2 Status

- **Branch:** `feat/ledgerguard-v2`
- **Branch Base:** `feat/operator-console-redesign` (`16db6617e10e6849fb34d7307a2519564907eaa0`)
- **Starting SHA:** `16db6617e10e6849fb34d7307a2519564907eaa0`
- **Origin/main SHA:** `24319b8006f64c3a84828658709212f9db9cde46`
- **PR #1 (`feat/operator-console-redesign`):** Open (Draft) at `16db6617e10e6849fb34d7307a2519564907eaa0`
- **Current Stage:** Stage 2 — Automated chaos campaign engine (Complete)
- **Next Stage:** Stage 3 — TLA+ formal specification

## Stage Checklist

- [x] **Stage 0:** Repository and branch preparation
- [x] **Stage 1:** Independent reference model and history checker
- [x] **Stage 2:** Automated chaos campaign engine
- [ ] **Stage 3:** TLA+ formal specification
- [ ] **Stage 4:** Tamper-evident audit journal
- [ ] **Stage 5:** End-to-end OpenTelemetry tracing
- [ ] **Stage 6:** Explainable recovery diagnostics
- [ ] **Stage 7:** As-of-time balance reconstruction
- [ ] **Stage 8:** Reversals, refunds and chargebacks
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
