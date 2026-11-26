# Historical As-of-Time Balance Reconstruction

## Overview

LedgerGuard V2 reconstructs historical posted, held, and available balances at any timestamp `T` (`src/ledgerguard/history/reconstruction.py`) using immutable checksummed `balance_snapshots` (`migrations/ledger/008_balance_snapshots.sql`) combined with deterministic sequence-ordered journal and hold replay.

## Guarantees

- **Deterministic Ordering:** Equal timestamps are broken deterministically by `(created_at ASC, sequence_number ASC, journal_id ASC, line_no ASC)`.
- **Snapshot Integrity:** Every snapshot stores a canonical SHA-256 checksum; corrupted snapshots are detected (`SNAPSHOT_CORRUPTED`) and safely fall back to full replay.
- **Pre-Creation Rejection:** Queries for timestamps prior to `ledger_accounts.created_at` are rejected.
- **Incomplete History:** Unreachable ledgers return `INCOMPLETE` rather than fabricating zero balances.
