# ADR 0002: Application-Level Reserve/Confirm/Cancel (TCC-Style) Protocol and Forward Recovery Invariant

## Status
Accepted

## Context
When customer accounts reside across physically independent database instances, transfers cannot execute within a single ACID transaction. The system requires a distributed coordination mechanism to guarantee that funds are neither lost nor duplicated in the event of process crashes, network partitions, or transient coordinator outages.

A key architectural question is whether to use PostgreSQL's database-native prepared transactions (`PREPARE TRANSACTION` / `COMMIT PREPARED`) or an application-level coordination protocol. Database-native 2PC holds physical database connection locks and row locks indefinitely across network round-trips, creating severe lock contention, deadlock risks across independent nodes, and cascading resource exhaustion if the coordinator dies mid-flight.

## Decision
1. **Application-Level Reserve/Confirm/Cancel Protocol (TCC-Style):**
   - The transfer protocol is explicitly classified as **application-level reserve/confirm/cancel coordination (Try-Confirm-Cancel)**, rather than database-native prepared-transaction 2PC.
   - It does **not** invoke PostgreSQL `PREPARE TRANSACTION` or `COMMIT PREPARED`, and does **not** provide global serializable isolation across databases.
   - Each phase and participant command executes as a **locally atomic database transaction** that commits immediately on its respective PostgreSQL instance.
   - **Phase 1 (Reserve / Try):**
     - Source participant executes `source_prepare`: reserves funds by creating an `ACTIVE` record in `holds` and decreasing available balance. The local transaction commits immediately.
     - Destination participant executes `destination_prepare`: validates recipient viability and registers an incoming `PREPARED` intent. The local transaction commits immediately.
   - **Decision Point:**
     - Coordinator atomically writes a durable decision (`COMMIT` or `CANCEL`) into the `transfer_decisions` table before initiating Phase 2.
     - Decision rows are protected by row-level locks and unique constraints, enforcing mutual exclusion and immutability.
   - **Phase 2 (Confirm / Settle):**
     - **Source-First Confirmation:** Source participant executes `source_confirm` first, consuming the hold and posting a balanced double-entry journal (Debit Cash/Credit Clearing).
     - **Destination Confirmation:** Destination participant executes `destination_confirm`, posting a balanced double-entry journal (Debit Clearing/Credit Recipient Wallet).
2. **Forward Recovery Invariant:**
   - Once a `COMMIT` decision is durably logged, the transfer **must recover forward to settlement**.
   - Under no circumstances will a post-COMMIT failure trigger an automatic cancellation, rollback, or unilateral refund.
   - Background orchestrator workers scan interrupted transfers in `COMMITTING` status and re-execute Phase 2 confirmations until completion.
3. **Cross-Database Visibility & Availability Tradeoffs:**
   - Visibility is **not globally atomic**: an observable window exists between source settlement and destination settlement where funds reside legitimately in inter-ledger clearing.
   - Coordinator loss or network partition temporarily leaves funds reserved in hold status without unilateral hold expiry; recovery resumes when connectivity restores.

## Consequences
- **Positive:** No physical database locks or open transactions are held across network I/O; participant ledgers remain highly responsive under concurrency.
- **Positive:** Destination credits are never revoked after commitment; customers are never exposed to phantom overdrafts caused by rollback of committed payments.
- **Positive:** Interrupted transfers remain resilient to prolonged coordinator outages, with source funds safely held in escrow until connectivity restores.
- **Negative:** Coordinator crashes during Phase 2 leave source funds in a reserved hold state until the recovery worker resumes forward execution.
- **Negative:** Cross-database visibility is eventually consistent, requiring reconciliation to account for explainable in-flight clearing movements.
