# Tamper-Evident Audit Journal

## Overview

LedgerGuard V2 appends a canonical SHA-256 hash chain to `journal_headers` (`migrations/ledger/007_tamper_evident_journal_chain.sql`) and attests periodic Merkle checkpoints in the separate Coordinator trust boundary (`migrations/coordinator/005_journal_checkpoint_attestations.sql`).

## Canonical Hash Formula

```text
entry_hash = SHA256(
    "LEDGERGUARD_JOURNAL_V1"
    || "|" || schema_version
    || "|" || ledger_id
    || "|" || sequence_number
    || "|" || previous_hash
    || "|" || journal_id
    || "|" || utc_timestamp
    || "|" || operation_type
    || "|" || currency
    || "|" || transfer_id
    || "|" || ordered_lines_canonical
)
```

- All monetary amounts use integer paise (`amount_minor`).
- `seal_journal_entry()` runs as a deferred constraint trigger under `SECURITY DEFINER`, locking `journal_chain_head` (`FOR UPDATE`) to serialize concurrent appends safely.
- `ledgerguard_app` and `ledgerguard_reporter` cannot update or delete `journal_headers`, `journal_lines`, or `journal_chain_head`.
- This is a **cryptographic tamper-evident audit log** across PostgreSQL trust boundaries, not a decentralized blockchain.

## CLI Commands

```bash
uv run python -m ledgerguard.cli verify-journal-chain --ledger ledger-1
uv run python -m ledgerguard.cli create-journal-checkpoint --ledger ledger-1
uv run python -m ledgerguard.cli verify-journal-checkpoint --ledger ledger-1
uv run python -m ledgerguard.cli verify-all-ledgers
./scripts/demo_tamper_detection.sh
```
