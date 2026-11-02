# LedgerGuard Data Models & Database Schemas

## 1. Entity Relationship (ER) Model

LedgerGuard maintains segregated schemas across the Coordinator database and independent Participant Ledger databases:

```mermaid
erDiagram
    %% Coordinator Database
    CUSTOMERS ||--o{ ACCOUNT_DIRECTORY : owns
    ACCOUNT_DIRECTORY ||--o{ TRANSFERS : routes
    TRANSFERS ||--o| TRANSFER_DECISIONS : commits
    TRANSFERS ||--o{ WORKFLOW_EVENTS : emits
    TRANSFERS ||--o{ OUTBOX_EVENTS : enqueues

    CUSTOMERS {
        uuid customer_id PK
        varchar name
        varchar email UK
        varchar status
        timestamptz created_at
    }

    ACCOUNT_DIRECTORY {
        uuid account_id PK
        uuid customer_id FK
        varchar ledger_id
        varchar currency
        varchar status
        int version
    }

    TRANSFERS {
        uuid transfer_id PK
        varchar idempotency_key UK
        uuid source_account_id
        uuid destination_account_id
        bigint amount_minor
        varchar currency
        varchar state
        timestamptz created_at
    }

    TRANSFER_DECISIONS {
        uuid transfer_id PK
        varchar decision
        text reason
        timestamptz decided_at
    }

    %% Participant Ledger Database
    LEDGER_ACCOUNTS ||--|| ACCOUNT_BALANCES : tracks
    LEDGER_ACCOUNTS ||--o{ JOURNAL_LINES : references
    JOURNAL_HEADERS ||--|{ JOURNAL_LINES : contains
    LEDGER_ACCOUNTS ||--o{ HOLDS : reserves
    LEDGER_ACCOUNTS ||--o{ TRANSFER_INTENTS : participates

    LEDGER_ACCOUNTS {
        uuid account_id PK
        uuid customer_id
        varchar ledger_id
        varchar currency
        varchar account_type
        varchar status
    }

    ACCOUNT_BALANCES {
        uuid account_id PK
        bigint posted_balance_minor
        bigint held_amount_minor
        bigint account_sequence
        bigint version
    }

    JOURNAL_HEADERS {
        uuid journal_id PK
        uuid transfer_id
        varchar operation_type
        varchar currency
        timestamptz created_at
    }

    JOURNAL_LINES {
        uuid line_id PK
        uuid journal_id FK
        int line_no
        uuid account_id FK
        varchar side
        bigint amount_minor
        bigint account_sequence
    }

    HOLDS {
        uuid hold_id PK
        uuid account_id FK
        uuid transfer_id
        bigint amount_minor
        varchar status
    }

    TRANSFER_INTENTS {
        uuid transfer_id PK
        varchar direction
        uuid source_account_id
        uuid destination_account_id
        bigint amount_minor
        varchar status
    }
```

---

## 2. Table Semantics & Constraints

### 2.1. Participant Ledger Tables

- **`ledger_accounts`**: The authoritative registry of accounts residing on this ledger instance.
  - Types: `LIABILITY` (customer wallets), `ASSET` (platform cash), `CONTROL` (clearing).
  - Normal Sides: `LIABILITY` $\rightarrow$ CREDIT, `ASSET` $\rightarrow$ DEBIT, `CONTROL` $\rightarrow$ CREDIT.
  - Statuses: `ACTIVE`, `FROZEN`, `CLOSED`.
- **`account_balances`**: High-performance row-level lock target and balance cache.
  - `posted_balance_minor`: Sum of debits and credits posted via confirmed journals.
  - `held_amount_minor`: Sum of active holds (`CHECK (held_amount_minor >= 0)`).
  - Customer spendability invariant: $\text{posted} - \text{held} \ge 0$.
- **`journal_headers` & `journal_lines`**: Immutable append-only double-entry financial records.
  - Immutability enforced by `reject_journal_mutation()` trigger.
  - Deferred trigger `trg_verify_journal_balanced` asserts that every committed journal has $\ge 2$ lines and net sum $= 0$.
  - Ordered index `idx_journal_lines_account_seq (account_id, account_sequence)` enables constant-time statement pagination.
- **`holds`**: Durable escrow reservations created during Phase 1 prepare.
  - Statuses: `ACTIVE`, `RELEASED`, `CONSUMED`.
- **`transfer_intents`**: Local participant knowledge of in-flight distributed transfers.
  - Stores `CANCELLED` tombstones when cancellation arrives before prepare.
- **`command_inbox`**: Deduplication barrier for participant commands (at-least-once delivery with single financial effect).
  - Unique constraint on `command_id` ensures deduplicated execution and idempotent response replay.
- **`participant_outbox`**: Transactional outbox table for event dispatch.

### 2.2. Coordinator Tables

- **`customers`**: Platform customer profiles with unique email constraints.
- **`account_directory`**: Three-state account provisioning table (`PROVISIONING`, `READY`, `DECOMMISSIONED`).
- **`api_idempotency`**: Public API idempotency cache storing SHA-256 canonical payload fingerprints.
- **`transfers`**: Distributed transfer lifecycle tracker (`ACCEPTED`, `PREPARING`, `COMMITTING`, `SETTLED`, `CANCELLING`, `CANCELLED`).
- **`transfer_decisions`**: Durable decision log recording `COMMIT` or `CANCEL` under row locks.
