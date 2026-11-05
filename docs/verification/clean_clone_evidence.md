# Isolated Clean-Clone Verification Evidence

**Verification Date:** November 5, 2026  
**Git Branch:** `feat/operator-console-redesign`  
**Verified Commit SHA:** `76d4e3c6b14ea184dbcc552353e906446221dc41`  
**Execution Environment:** Isolated macOS Darwin environment with dedicated Docker container network and fresh anonymous volumes.

---

## 1. Isolation & Fresh Volume Guarantee

Clean-clone verification was performed using a dedicated, isolated project namespace:
- **`COMPOSE_PROJECT_NAME`:** `ledgerguard_iso_verify_001`
- **Initial Volume State:** Explicitly purged using `docker compose -p ledgerguard_iso_verify_001 down -v`.
- **Pre-migration Table State:** Queried `coordinator_db`, `ledger1_db`, and `ledger2_db` via `psql` before applying migrations. Confirmed `Did not find any relations.` (zero tables or migrations existed).
- **Post-verification Teardown:** All containers and volumes (`ledgerguard_iso_verify_001_coordinator_data`, `ledgerguard_iso_verify_001_ledger1_data`, `ledgerguard_iso_verify_001_ledger2_data`) were torn down with `-v` upon completion.

---

## 2. Frozen Dependency Installation

Installed exclusively from frozen dependency locks:
1. **Python Virtual Environment:**
   ```bash
   uv sync --frozen --extra dev
   ```
   *Result:* Installed 50 pinned packages into clean `.venv` in 159ms with zero lock modifications.
2. **Frontend Packages:**
   ```bash
   cd apps/console && npm ci
   ```
   *Result:* Added 323 packages strictly adhering to `package-lock.json`.

---

## 3. Database Migration Sequence

Every migration was applied sequentially from scratch via `uv run python -m ledgerguard.cli migrate --target all`:

| Database | Applied Migrations | Status |
| :--- | :--- | :--- |
| **Coordinator DB** | `001_initial_coordinator_schema.sql`<br>`002_workflow_events_unique_constraint.sql`<br>`003_operator_auth_schema.sql`<br>`004_harden_auth_schema_and_permissions.sql` | Applied cleanly |
| **Participant Ledger 1** | `001_initial_schema.sql`<br>`002_posting_function.sql`<br>`003_account_status_functions.sql`<br>`004_local_transfers_and_idempotency.sql`<br>`005_intents_holds_inbox_outbox.sql`<br>`006_closure_unresolved_obligations.sql` | Applied cleanly |
| **Participant Ledger 2** | `001_initial_schema.sql`<br>`002_posting_function.sql`<br>`003_account_status_functions.sql`<br>`004_local_transfers_and_idempotency.sql`<br>`005_intents_holds_inbox_outbox.sql`<br>`006_closure_unresolved_obligations.sql` | Applied cleanly |

### Role Privilege & Security Boundary Verification
- **`ledgerguard_reporter` Isolation:** Denied `SELECT` on `operators`, `operator_sessions`, and `operator_login_attempts`.
- **`ledgerguard_app` Least Privilege:** Denied `DELETE` on `operators`; denied `UPDATE` and `DELETE` on `operator_login_attempts` (guaranteeing append-only audit trail).
- **Token Hashing at Rest:** Confirmed `operator_sessions.session_token_hash` stores 64-character SHA-256 digests (`character varying(64)`).

---

## 4. Runtime Operator Provisioning

Synthetic operator provisioned using non-interactive protected standard input:
```bash
read -rsp "Temporary operator password: " LEDGERGUARD_TEMP_PASSWORD
printf '\n'
printf '%s\n' "$LEDGERGUARD_TEMP_PASSWORD" | \
  uv run python -m ledgerguard.cli create-operator \
    --username clean_op \
    --email clean_op@test.internal \
    --role ADMIN \
    --stdin-password
unset LEDGERGUARD_TEMP_PASSWORD
```
*Result:* Operator created with Argon2id password hash (`ID=291e7fe3-2129-46a1-b81f-9818162a22f3`).

---

## 5. Automated Verification Results

### A. Backend Pytest Suite
```bash
uv run pytest -ra -W error
```
*Result:* **74 passed in 14.55s** (100% passing across accounting invariants, distributed failure scenarios, concurrency safety, and auth boundaries).

### B. Code Quality & Static Type Verification
```bash
uv run ruff check .
uv run mypy src
```
*Result:*
- **Ruff:** All checks passed with zero linter errors.
- **Mypy:** Success: no issues found in 35 source files.

### C. Frontend Unit Test Suite
```bash
cd apps/console && npm test
```
*Result:* **45 passed across 18 suites in 392ms** (safe return URLs, financial arithmetic, session timeout models, workflow events).

### D. Real Browser Playwright E2E & Accessibility Suite
```bash
cd apps/console && npx playwright test
```
*Engines Tested:* **Chromium**, **Firefox**, **WebKit**  
*Result:* **72 passed across 3 browser engines (24 tests per engine) in 2.4m**
- Real browser authentication lifecycle: password login, MFA challenge, TOTP replay rejection, session refresh retention, logout, expired session redirection to `/login`, nested route access, CSRF rejection, keyboard-only login, reduced-motion preferences.
- Rendered Axe accessibility audit (`@axe-core/playwright`): 0 critical or serious violations across `/`, `/login`, MFA challenge, `/console`, `/console/transfers/[transferId]`, `/console/reconciliation`, `/console/experiments`.

### E. Next.js Production Build
```bash
cd apps/console && npm run build
```
*Result:* Compiled successfully in 4.9s; all 13 routes generated without errors.

### F. Dependency Security Audits
1. **Python Production Graph:**
   ```bash
   uv export --frozen --no-dev --no-hashes --no-emit-project -o /tmp/ledgerguard-production-requirements.txt
   uv tool run pip-audit -r /tmp/ledgerguard-production-requirements.txt
   ```
   *Result:* **No known vulnerabilities found** across 31 production packages.
2. **Node Production Graph:**
   ```bash
   cd apps/console && npm audit --omit=dev
   ```
   *Result:* **found 0 vulnerabilities**.

### G. Signature TCC Failure Recovery Demo
```bash
./scripts/demo_signature_recovery.sh
```
*Result:* **All 8 steps completed successfully**:
1. Isolated participant provisioning (Alice ₹1,000, Bob ₹0)
2. Injected crash `FAIL_AFTER_COMMIT_BEFORE_SOURCE_CONFIRM` during ₹400 transfer
3. Verified invariants during outage (durable hold ₹400 maintained, zero premature refund)
4. Forward autonomous recovery executed by orchestrator worker (transfer settled)
5. End-state balances verified: Alice ₹600, Bob ₹400, Net clearing ₹0.00
6. Idempotency replay check confirmed zero duplicate financial effect
7. Command receipts & participant journal entries verified
8. Stopped-and-drained cluster audit passed with 0 findings across 14 transfers.

### H. Repository Security & Privacy Scanner
```bash
python3 scripts/security_audit_scanner.py
```
*Result:* **SCAN PASSED: All checks passed** (zero tracked secrets, zero personal emails, zero local filesystem paths, zero uncommitted credential artifacts).

---

## 6. Teardown Confirmation

```bash
docker compose -p ledgerguard_iso_verify_001 down -v
```
All 3 PostgreSQL 17 containers, default network, and volumes were removed completely.
