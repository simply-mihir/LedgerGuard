# LedgerGuard V2 Invariant Catalogue

Every stage of LedgerGuard V2 must preserve the following invariants (`I1`–`I16`). Machine-readable definitions live in [`src/ledgerguard/domain/invariants.py`](../src/ledgerguard/domain/invariants.py).

| ID | Name | Specification | Enforcement / Verification |
| :--- | :--- | :--- | :--- |
| **I1** | Balanced Journal | Every posted journal transaction balances exactly: $\sum \text{debits} = \sum \text{credits}$. | `trg_verify_journal_balanced` trigger + reference model |
| **I2** | Integer Paise | Money is represented as integer paise (`BIGINT`). No floating-point financial arithmetic. | `AmountPaise` domain type + `BIGINT` columns |
| **I3** | Non-Negative Available Balance | Available balance ($\text{posted} - \text{held}$) never becomes negative for customer wallets. | `post_journal` / `source_prepare` row locks + `CHECK` |
| **I4** | API Idempotency | One idempotency key produces at most one financial effect. | `api_idempotency` unique key + payload hash |
| **I5** | Participant Command Deduplication | One participant command produces at most one participant effect. | `command_inbox` unique `command_id` |
| **I6** | Irreversible Commit | A durable `COMMIT` decision never changes to `CANCEL`. | `transfer_decisions` row lock + immutability |
| **I7** | Irreversible Cancel | A durable `CANCEL` decision never changes to `COMMIT`. | `transfer_decisions` row lock + immutability |
| **I8** | Forward Settlement Liveness | A committed transfer eventually settles once required components recover. | Recovery worker + TLA+ liveness + chaos |
| **I9** | Cancelled Transfer Non-Settlement | A cancelled transfer never settles. | Decision guard + reference model + TLA+ |
| **I10** | Tombstone Blocks Delayed Prepare | A cancellation tombstone prevents delayed `prepare` from recreating a hold. | `transfer_intents` `CANCELLED` check |
| **I11** | Journal Immutability | Posted journal entries cannot be updated or deleted through ordinary roles. | `reject_journal_mutation()` trigger + role grants + hash chain |
| **I12** | Compensating Corrections | Reversal and refund operations create compensating entries; they never erase history. | Compensating journal postings |
| **I13** | Zero-Sum Clearing Conservation | Aggregate cross-ledger clearing delta equals zero in a completed, fully reachable, stopped-and-drained audit. | Reconciliation engine + reference model |
| **I14** | No False Healthy Audit | An incomplete audit (e.g., unreachable database) must never report a healthy `PASS` result. | Reachability probe `INCOMPLETE` gate |
| **I15** | Secret Redaction | Authentication secrets, raw session tokens, and TOTP secrets never appear in APIs, logs, or screenshots. | Auth service + OTel redaction + security scanner |
| **I16** | Reporter Role Isolation | The `ledgerguard_reporter` role cannot read authentication tables. | Migration 004 `REVOKE` + permission tests |
