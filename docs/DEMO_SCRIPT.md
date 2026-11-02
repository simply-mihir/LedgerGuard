# LedgerGuard: Portfolio Demonstration & Recording Script

This document provides the complete, reproducible 3-to-5 minute demonstration walkthrough for LedgerGuard. It is designed for live portfolio presentations, video recordings, and technical interviewer walkthroughs.

---

## 1. Pre-Recording Preparation & Privacy Checklist

Before beginning the demonstration or starting screen capture:

- [ ] **Notification Hygiene:** Enable "Do Not Disturb" on macOS (System Settings > Focus > Do Not Disturb).
- [ ] **Terminal Sanitization:** Use a clean, non-revealing prompt without username or private local paths:
  ```bash
  export PS1="ledgerguard$ "
  ```
- [ ] **Browser Sanitization:**
  - Open a dedicated Chrome or Firefox window in Incognito/Private mode.
  - Close all unrelated tabs and hide the bookmarks bar (`Cmd + Shift + B`).
  - Open `http://localhost:3300` (Next.js Operator Console) at 100% zoom.
- [ ] **Display Setup:** Arrange windows side-by-side:
  - Left Half (50% width): Terminal window running the demonstration script.
  - Right Half (50% width): Browser window displaying the LedgerGuard Operator Console.
- [ ] **Environment Verification:** Confirm Docker PostgreSQL containers are running and healthy:
  ```bash
  docker compose ps
  ```

---

## 2. Spoken Walkthrough & Demo Script (3–5 Minutes)

### Phase 1: Introduction & System Architecture (0:00 – 0:45)

**Spoken Narrative:**
> "Hello! Today I'm demonstrating LedgerGuard, a distributed double-entry financial ledger built for wallet and inter-ledger settlement. 
> 
> Unlike typical distributed transaction demos that rely on shared database schemas or 2PC locks held across the network, LedgerGuard coordinates transfers across three completely independent PostgreSQL 17 failure domains: a central Coordinator and two autonomous Participant Ledgers, Ledger 1 and Ledger 2.
>
> In financial systems, the cardinal rule after a transaction reaches a durable COMMIT decision is that you must always recover forward. You can never automatically refund or rollback just because a network timeout occurs after money was committed. Let's see this in action."

**Visual Action:**
- Show the Operator Console Overview screen at `http://localhost:3300`.
- Point out the active ledger cards: **Coordinator DB (:5442)**, **Ledger 1 DB (:5443)**, and **Ledger 2 DB (:5444)**.

---

### Phase 2: Provisioning, Seeding & Injected Coordinator Crash (0:45 – 2:00)

**Terminal Command:**
```bash
./scripts/demo_signature_recovery.sh
```

**Expected Visible Output:**
```text
===========================================================================
  LEDGERGUARD SIGNATURE FAILURE SCENARIO: INTERRUPTED 2PC RECOVERY
===========================================================================

[STEP 1] Provisioning Isolated Participants & Seeding Accounts
  • Source Customer:      Alice on Ledger 1 (uuid)
    - Posted Balance:     ₹1,000.00
    - Available Balance:  ₹1,000.00
    - Active Holds:       ₹0.00
  • Destination Customer: Bob on Ledger 2 (uuid)
    - Posted Balance:     ₹0.00
    - Available Balance:  ₹0.00

[STEP 2] Executing 2PC Cross-Ledger Transfer (₹400.00) with Failpoint
  • Injected Fault: FAIL_AFTER_COMMIT_BEFORE_SOURCE_CONFIRM
  ⚡ CRASH INJECTED: Simulated coordinator crash immediately after durable COMMIT.
```

**Spoken Narrative:**
> "In Step 1, the script registers two distinct customers on separate ledgers: Alice on Ledger 1 and Bob on Ledger 2. Alice is seeded with ₹1,000.00 via a balanced, immutable funding journal.
>
> In Step 2, Alice initiates a ₹400.00 cross-ledger transfer to Bob. Both ledgers successfully prepare: Ledger 1 creates an active hold reserving ₹400.00 from Alice's available balance, and Ledger 2 validates Bob's account viability.
>
> Right as the Coordinator durably commits the decision to disk, we inject a catastrophic failure: `FAIL_AFTER_COMMIT_BEFORE_SOURCE_CONFIRM`. The coordinator crashes before either participant receives confirmation."

---

### Phase 3: Inspecting Invariants During the Outage (2:00 – 2:45)

**Expected Visible Output:**
```text
[STEP 3] Inspecting Invariants During Coordinator Outage
  1. Coordinator Transfer State:   COMMITTING
  2. Coordinator Durable Decision: COMMIT (Committed to disk)
  3. Alice (Ledger 1) Hold:        ₹400.00 (Reserved, NOT refunded)
  4. Alice Available Spendability: ₹600.00
  5. Bob (Ledger 2) Balance:       ₹0.00 (Awaiting Phase 2 confirmation)

  ✓ ALL INVARIANTS SATISFIED DURING CRASH: Zero premature refund, durable reservation held.
```

**Spoken Narrative:**
> "Now, look at the system state during the simulated crash in Step 3. Notice three critical financial invariants:
> 
> First, on the Coordinator, the decision table records an immutable `COMMIT`.
> Second, on Ledger 1, Alice's ₹400.00 is NOT refunded; it remains in an active hold, reducing her available spendability to ₹600.00 so she cannot double-spend.
> Third, on Ledger 2, Bob has not yet been credited, because confirmation hasn't happened.
>
> The system has halted cleanly at the exact crash boundary without leaking funds or making false assumptions."

---

### Phase 4: Autonomous Forward Recovery & Settlement (2:45 – 3:30)

**Expected Visible Output:**
```text
[STEP 4] Starting Autonomous Worker Forward Recovery
  Orchestrator discovers transfer in COMMITTED state:
  Applying source-first settlement on Ledger 1 -> Settlement on Ledger 2.
  ✓ Forward Recovery Result: Transfer <id> status = SETTLED

[STEP 5] Verifying Final End-State Balances & Clearing Invariant
  • Alice on Ledger 1:
    - Posted Balance:    ₹600.00 (Expected: ₹600.00)
    - Active Holds:      ₹0.00 (Expected: ₹0.00)
    - Available:         ₹600.00
  • Bob on Ledger 2:
    - Posted Balance:    ₹400.00 (Expected: ₹400.00)
    - Available:         ₹400.00
  • Inter-Ledger Clearing Movement:
    - Ledger 1 Clearing Delta: -₹400.00
    - Ledger 2 Clearing Delta: ₹400.00
    - Net Clearing Delta:      ₹0.00 (Exact Conservation)
```

**Spoken Narrative:**
> "In Step 4, the autonomous background orchestrator detects the in-flight transfer. Because a durable `COMMIT` was already logged, the worker knows rollback is illegal. It initiates **forward recovery**.
>
> Following our strict source-first discipline, it executes settlement on Ledger 1 first—consuming Alice's hold and debiting the clearing account—and then credits Bob on Ledger 2.
>
> In Step 5, we verify end-state balances: Alice has ₹600.00 with zero residual holds, Bob has ₹400.00, and our inter-ledger clearing balances to exactly zero paise."

---

### Phase 5: Client Idempotency & Journal Immutability (3:30 – 4:15)

**Expected Visible Output:**
```text
[STEP 6] Demonstrating External Client Idempotency Retry
  • Retrying transfer submission with identical idempotency key: demo-tx-<id>
  • Retry Response Status: SETTLED
  • Matched Transfer ID:   <id>
  ✓ Zero Duplicate Financial Effect: Balances unchanged after repeated client retry.

[STEP 7] Inspecting Participant Journal Entries and Command Receipts
  • Ledger 1 (Source) Journals for Transfer:      1 (Expected: 1 settlement journal)
  • Ledger 1 (Source) Inbox Receipts for Transfer: 2 (Prepare + Confirm receipts)
  • Ledger 2 (Dest) Journals for Transfer:        1 (Expected: 1 settlement journal)
  • Ledger 2 (Dest) Inbox Receipts for Transfer:   2 (Prepare + Confirm receipts)
```

**Spoken Narrative:**
> "What happens if a network-timeout caused the client to resend the original transfer request?
>
> In Step 6, we re-execute the transfer with the identical `Idempotency-Key`. The coordinator matches the canonical payload fingerprint, detects the completed state, and returns `SETTLED` immediately without touching account balances.
>
> Furthermore, in Step 7, we query each participant's immutable `journal_headers` and `command_inbox`. There is exactly one settlement journal and durable command receipt on each ledger—guaranteeing zero duplicate financial effects."

---

### Phase 6: Multi-Database Audit & Wrap-Up (4:15 – 5:00)

**Expected Visible Output:**
```text
[STEP 8] Executing Final Stopped-and-Drained Cross-Ledger Audit
  • Audit Status:         PASS
  • Audit Coverage:       FULL
  • Reachable Ledgers:    coordinator, ledger-1, ledger-2
  • Transfers Examined:   <count>
  • Findings Count:       0

===========================================================================
  DEMO COMPLETED SUCCESSFULLY: ZERO FUNDS LOST, FORWARD RECOVERY VERIFIED
===========================================================================
```

**Visual Action:**
- Switch to the Operator Console **Reconciliation** screen (`http://localhost:3300`).
- Show the `PASS` badge, green checkmarks across all three databases, zero unresolved discrepancies, and balanced clearing.

**Spoken Narrative:**
> "Finally, in Step 8, we trigger a stopped-and-drained cross-database reconciliation audit. It verifies double-entry balance constraints on every ledger, confirms all holds are released, and validates that total clearing sum across independent databases is exactly zero.
>
> That completes the demonstration: immutable journals, durable application-level coordination, crash recovery, and continuous reconciliation—running live across independent PostgreSQL 17 instances. Thank you!"

---

## 3. Operator Console Screens to Display

| Screen | URL | What to Highlight |
| :--- | :--- | :--- |
| **System Overview** | `http://localhost:3300` | Real-time connectivity to Coordinator (:5442), Ledger 1 (:5443), Ledger 2 (:5444). |
| **Accounts** | `http://localhost:3300` (Accounts Tab) | Alice's posted balance (₹600.00) vs Bob's posted balance (₹400.00), with 0 held amount. |
| **Transfers** | `http://localhost:3300` (Transfers Tab) | Settled status, cross-ledger transfer type, canonical payload hash. |
| **Audit & Reconciliation** | `http://localhost:3300` (Audit Tab) | Full coverage badge, zero findings, clearing sum = ₹0.00. |

---

## 4. Troubleshooting & Recovery FAQ

### Port Conflicts (5442, 5443, 5444, or 3300)
If Docker ports are in use by other local services:
```bash
lsof -i :5442 -i :5443 -i :5444 -i :3300
```
Stop competing services or adjust port mappings in `.env` and `docker-compose.yml`.

### Recreating Disposable Test Databases
If you want to run the demonstration from an empty state:
```bash
docker compose down -v
docker compose up -d
sleep 3
uv run python -m ledgerguard.cli migrate --target all
./scripts/demo_signature_recovery.sh
```

### Running Verification Tests Before Demo
Confirm that all unit and integration tests pass cleanly:
```bash
uv run pytest -ra -v
```
All 54 tests should pass with zero warnings.
