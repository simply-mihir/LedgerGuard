# LedgerGuard

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![PostgreSQL 17](https://img.shields.io/badge/postgresql-17-blue.svg)](https://www.postgresql.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![Next.js 15](https://img.shields.io/badge/Next.js-15-black.svg)](https://nextjs.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

LedgerGuard is a portfolio implementation of a double-entry wallet ledger that demonstrates immutable journals, concurrency-safe spending, idempotent APIs, durable application-level transfer coordination (TCC-style reserve/confirm/cancel), failure recovery, and multi-database reconciliation.

---

## 1. System Topology & Core Invariants

LedgerGuard operates across three isolated PostgreSQL 17 instances:
- **Coordinator Database (`coordinator_db` on host port 5442)**: Customer directory, idempotent routing, durable transfer decisions (`COMMIT` / `CANCEL`), and transaction outbox.
- **Participant Ledger 1 (`ledger1_db` on host port 5443)**: Independent accounting kernel, customer wallets, holds escrow, and Inter-Ledger Clearing Control.
- **Participant Ledger 2 (`ledger2_db` on host port 5444)**: Independent accounting kernel, customer wallets, incoming intents, and Inter-Ledger Clearing Control.

```
                     ┌──────────────────────────────────┐
                     │   Next.js 15 Operator Console    │
                     │       (http://localhost:3300)    │
                     └─────────────────┬────────────────┘
                                       │ HTTP / Operator APIs
                                       ▼
                     ┌──────────────────────────────────┐
                     │       FastAPI Coordinator        │
                     │       (http://localhost:8010)    │
                     └───────┬──────────────┬───────────┘
                             │              │
           Phase 1 & 2 TCC   │              │   Phase 1 & 2 TCC
         (Source Prepare/    │              │ (Dest Prepare/
             Confirm)        │              │     Confirm)
                             ▼              ▼
                    ┌────────────────┐  ┌────────────────┐
                    │ Ledger 1 DB    │  │ Ledger 2 DB    │
                    │ (Port 5443)    │  │ (Port 5444)    │
                    └────────────────┘  └────────────────┘
```

### Financial Invariants that Survive Every Refactor

1. **Integer Minor Units (Paise, INR):** Bounded positive integers `[1, 100_000_000_000]`. Floating-point conversion and float/boolean types are strictly rejected.
2. **Double-Entry Bookkeeping:** Every committed journal has $\ge 2$ lines and balances to exact zero per currency (`trg_verify_journal_balanced`).
3. **Database Engine Immutability:** Financial tables (`journal_headers`, `journal_lines`) reject `UPDATE`, `DELETE`, and `TRUNCATE` operations via database mutation triggers. The application connection role (`ledgerguard_app`) is denied direct table DML and must invoke stored procedures (`post_journal`, `update_account_status`).
4. **Deterministic Account Locking:** Account balances are locked in sorted order (`account_id ASC`) inside PL/pgSQL stored procedures. Network calls never occur inside locked transactions.
5. **Application-Level Reserve/Confirm/Cancel Coordination:** Source prepare reserves funds (creates `ACTIVE` hold); destination prepare accepts incoming obligation. Once coordinator decision `COMMIT` is durably written, the engine **recovers forward to settlement**. Rollbacks or refunds after `COMMIT` are architecturally prohibited. (Note: Relies on locally atomic database transactions on each participant, not PostgreSQL `PREPARE TRANSACTION`).
6. **Durable Tombstone Semantics:** When `CANCEL` arrives before `PREPARE` due to message reordering, a durable `CANCELLED` tombstone is written, causing delayed prepare requests to reject with zero funds locked.
7. **In-Flight Obligation Protection:** Account closure (`CLOSED`) is strictly blocked if the account has a non-zero balance, active holds, or unresolved `PREPARED` transfer intents (`006_closure_unresolved_obligations.sql`).
8. **Cross-Ledger Clearing Conservation:** Inter-ledger clearing balances sum to zero across all participants:
   $$\sum_{i=1}^{N} \text{ClearingBalance}_i = 0$$

---

## 2. Prerequisites & Quickstart

### Prerequisites
- macOS or Linux
- Python 3.12+ with [`uv`](https://github.com/astral-sh/uv)
- Docker Engine & Docker Compose v2
- Node.js 20+ & npm

### Setup Environment
```bash
# Clone and enter directory
cd LedgerGuard

# Configure environment variables
cp .env.example .env

# Install Python dependencies with uv
uv sync --extra dev

# Install Next.js operator console dependencies from committed lockfile
cd apps/console && npm ci && cd ../..
```

> [!IMPORTANT]
> **Security Notice:** The passwords, secrets, and connection strings documented in `.env.example`, `docker-compose.yml`, and `docker/init-roles.sql` (e.g. `ledgerguard_app_secret`, `ledgerguard_admin_secret`) are strictly local development credentials intended for isolated offline evaluation and testing. They must be replaced with securely generated secrets outside isolated local use. By default, `docker-compose.yml` binds PostgreSQL host ports exclusively to loopback (`127.0.0.1`), and production mode strictly disables fault-injection APIs (`POST /v1/operator/experiments/run` returns HTTP 403 Forbidden). Real `.env` files are excluded by `.gitignore`.

### Launch PostgreSQL 17 Databases
```bash
# Start isolated containers for coordinator, ledger1, and ledger2 (bound to 127.0.0.1)
docker compose up -d

# Check container health status
docker compose ps
```

### Apply SQL Migrations
```bash
uv run python -m ledgerguard.cli db migrate
```

---

## 3. Running Verification & Acceptance Tests

Execute the complete test suite against live PostgreSQL 17 instances:

```bash
# Run all 54 automated integration, failure, and property tests
uv run pytest tests/ -v

# Run code style & lint checking
uv run ruff check .

# Run static type checking across all packages
uv run mypy src

# Build and validate Next.js operator console
cd apps/console && npm run build && cd ../..
```

### Test Suite Breakdown
| Test Suite | Tests | Description |
| :--- | :--- | :--- |
| `test_accounting_kernel.py` | 14 | Amount bounds, immutable journal triggers, role permissions, zero-balance closure. |
| `test_local_transfers.py` | 9 | Atomic local transfers, idempotency fingerprints, 100 concurrent withdrawals of 80 against 100, reversals. |
| `test_durable_workflow.py` | 7 | Transactional outbox engine, durable decisions, command inbox deduplication, holds lifecycle. |
| `test_distributed_failures.py` | 11 | Complete 2PC failure matrix: lost prepare replies, crash after COMMIT, crash between confirms, freeze/closure invariants, retry idempotency. |
| `test_audit_reconciliation.py` | 4 | Multi-database reachability probing, corrupted hold cache detection, stopped-and-drained audit. |
| `test_operator_api.py` | 5 | Operator REST endpoints, overview stats, timeline inspection, public-safe experiment blocking. |
| `test_reference_model.py` | 1 | Hypothesis property-based testing verifying execution agreement against a reference state model. |
| `test_smoke.py` | 3 | Real PostgreSQL 17 connectivity, migration tracking, and role boundary verification. |

---

## 4. Signature Scenario Demo: Interrupted 2PC Recovery

Execute the standalone, deterministic failure scenario script:

```bash
./scripts/demo_signature_recovery.sh
```

**Demonstration Sequence:**
1. Provisions Alice on Ledger 1 (funded with ₹1,000.00) and Bob on Ledger 2 (₹0.00).
2. Initiates cross-ledger transfer of ₹400.00 with failpoint `FAIL_AFTER_COMMIT_BEFORE_SOURCE_CONFIRM`.
3. Injects fatal coordinator crash immediately after the `COMMIT` decision is durably logged to disk.
4. Inspects interrupted state:
   - Coordinator Decision: Committed as `COMMIT`
   - Alice Hold on Ledger 1: ₹400.00 actively reserved (not refunded)
   - Alice Available: Reduced to ₹600.00
   - Bob on Ledger 2: Not yet credited
5. Starts autonomous forward recovery worker:
   - Slices through Phase 2 confirmations (source settlement $\rightarrow$ destination settlement).
6. Verifies final end-state:
   - Alice Final: ₹600.00, active hold: ₹0.00
   - Bob Final: ₹400.00 (exact single credit)
   - Inter-Ledger Clearing Delta: $\Delta L_1 + \Delta L_2 = 0$ (exact conservation).

---

## 5. Running Workload Benchmarks

Execute the automated benchmark runner:

```bash
uv run python scripts/run_benchmarks.py
```

- Measures **Uniform Workload** (32.1 TPS) vs **Hot-Account Workload** (38.2 TPS, 80% concentration) across 60 successful settled transfers each under a single-threaded sequential client.
- Discloses inferred **Acceptance Latency** (p50: ~7.1 ms) vs **Settlement Latency** (p50: ~18.5 ms).
- Executes `EXPLAIN (ANALYZE, BUFFERS)` query execution plans directly on PostgreSQL 17.
- Emits markdown baseline report to [`docs/benchmarks/baseline_report.md`](docs/benchmarks/baseline_report.md).

> In this sequential benchmark, the hot-account workload was slightly faster, likely because repeated access improved buffer and application-level locality while the single-threaded driver introduced no concurrent row-lock contention. The benchmark does not predict hot-account performance under concurrent load, where lock serialization may reduce throughput. Synchronous execution ensured 0 rejections and 0 retries; background queue-drain time was not separately benchmarked.

---

## 6. Running the Operator Console & API Server

### Start Coordinator API Server
```bash
uv run uvicorn ledgerguard.api.app:app --host 0.0.0.0 --port 8010 --reload
```

### Start Next.js Console
```bash
cd apps/console
npm run dev
```
Open **[http://localhost:3300](http://localhost:3300)** to view the 5 operator screens:
1. **Overview:** System topology, total ledgered assets, liabilities, clearing sum, reachability indicator.
2. **Accounts:** Multi-ledger account explorer with status filters and full double-entry statement modals.
3. **Transfer Explorer:** Transaction history with 2PC lifecycle stepper (Prepared, Decided, Confirmed, Settled).
4. **Reconciliation:** Real-time cross-database audit runner with Stopped-and-Drained verification.
5. **Experiments:** Interactive fault injection controls with live invariant inspection.

---

## 7. Architecture Documentation & Decision Records

Detailed specifications and architectural decision records are located in `docs/`:

- [ADR 0001: Immutable Double-Entry Journals & Role Segregation](docs/adr/0001-immutable-journals-and-role-separation.md)
- [ADR 0002: Two-Phase Commit & Forward Recovery Invariant](docs/adr/0002-two-phase-commit-and-forward-recovery.md)
- [ADR 0003: Durable Tombstone Semantics & Unresolved Obligations](docs/adr/0003-tombstone-semantics-and-unresolved-obligations.md)
- [ADR 0004: Multi-Database Reachability Probing & Clearing Reconciliation](docs/adr/0004-cross-ledger-clearing-reconciliation.md)
- [System Architecture Specification](docs/architecture/system_architecture.md)
- [2PC Protocol Specification & State Machines](docs/architecture/protocol_2pc.md)
- [Data Models & Database Schemas](docs/architecture/data_models.md)
- [Benchmark Baseline Report](docs/benchmarks/baseline_report.md)
- [Demonstration & Presentation Walkthrough Script](docs/DEMO_SCRIPT.md)

---

## 8. Honest Limitations & Disclosures

1. **Simulated Money Only:** LedgerGuard is a portfolio implementation demonstrating distributed systems and accounting primitives; it does not connect to live banking networks (UPI, IMPS, NEFT, SWIFT) or provide regulatory compliance.
2. **Single-Currency Baseline:** The current kernel baseline operates exclusively in Indian Rupee (`INR`) integer paise. Cross-currency foreign exchange requires an exchange-clearing leg.
3. **Host Port Mapping:** Host PostgreSQL ports are mapped to `5442` (coordinator), `5443` (ledger1), and `5444` (ledger2) to avoid port collisions with default PostgreSQL installations.
4. **No Global ACID Across Databases:** Each participant transaction commits locally in PostgreSQL. Cross-database atomicity is achieved at the application level via durable coordinator decisions and forward recovery; global serializable isolation across independent databases is not provided.
5. **Coordinator Outage Impact:** If the coordinator crashes or becomes unavailable during Phase 2, source funds remain reserved in an `ACTIVE` hold until the recovery orchestrator resumes execution.
6. **Local Single-Worker Benchmarks:** Benchmark results reflect single-worker sequential throughput on documented local hardware; multi-region production HA requires distributed consensus (e.g. Raft) and dedicated network infrastructure.

---

## 9. Portfolio Resume Bullets

- **Distributed Systems & Financial Ledgers:** "Architected and verified a multi-database financial ledger across 3 isolated PostgreSQL 17 instances, implementing double-entry accounting with PL/pgSQL row locks (`account_id ASC`), database mutation triggers, and TCC-style reserve/confirm/cancel coordination with 100% crash recovery and zero duplicate financial effects across 54 automated tests."
- **Data Engineering & Reliability:** "Engineered an idempotent transfer coordinator and continuous cross-database reconciliation engine that audits inter-ledger clearing ($\sum \text{clearing} = 0$) and active holds, achieving sub-millisecond indexed balance queries ($O(1)$) and 32–38 TPS sequential end-to-end settlement throughput on PostgreSQL 17."
