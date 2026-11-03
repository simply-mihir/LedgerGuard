# ADR 0001: Immutable Double-Entry Journals and Database Role Segregation

## Status
Accepted

## Context
A financial ledger must guarantee the auditability and integrity of all historical accounting events. Naive implementations frequently allow application services to execute generic CRUD operations, update account balances directly, or mutate journal entries in place. Such designs expose the ledger to accidental data corruption, unauthorized balance tampering, and undetectable reconciliation divergence.

## Decision
1. **Double-Entry Multi-Line Balancing:** Every financial transaction must be recorded as an immutable journal entry consisting of a `journal_headers` row and two or more `journal_lines` rows whose net sum across debits and credits is strictly zero in integer paise.
2. **Database Mutation Triggers:** Postgres trigger functions (`reject_journal_mutation()`) intercept and reject any `UPDATE`, `DELETE`, or `TRUNCATE` operations on `journal_headers` and `journal_lines`.
3. **Stored Procedure Boundary (`post_journal`):** Application code cannot insert journal lines directly. Financial postings must execute through the `post_journal` stored procedure, which enforces template validation, balance updates, and sequence increments atomically under `SECURITY DEFINER`.
4. **Deterministic Account Locking:** Within `post_journal`, involved account rows in `account_balances` are locked using `SELECT ... FOR UPDATE` ordered strictly by `account_id ASC`. This guarantees total deadlock freedom for concurrent multi-party transactions.
5. **Database Role Privileges:** The application connection role (`ledgerguard_app`) is denied table-level `INSERT`, `UPDATE`, `DELETE`, and `TRUNCATE` on `journal_headers`, `journal_lines`, and `account_balances`. It possesses only `EXECUTE` privileges on `post_journal` and `update_account_status`.

## Consequences
- **Positive:** Financial history is strictly append-only at the database engine level. Accidental or malicious balance modifications by application code are physically prohibited.
- **Positive:** Multi-account transfers execute without deadlocks under arbitrary concurrent thread interleaving.
- **Negative:** Adjustments or corrections require creating explicit linked compensating journal entries rather than modifying existing rows in-place.
