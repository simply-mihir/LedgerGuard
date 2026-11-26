# Disaster Recovery & Restore Verification

## Overview

LedgerGuard V2 verifies recovery from catastrophic database loss (`src/ledgerguard/dr/verify.py`) using isolated disposable databases, `pg_dump`/`pg_restore`, forward recovery replay, cryptographic journal-chain verification, Merkle checkpoint attestation checks, and stopped-and-drained cross-ledger reconciliation.

## Safety Guards

- `run_disposable_dr_drill()` and `scripts/demo_disaster_recovery.sh` refuse to run without explicit disposable confirmation (`--confirm-disposable` / `confirm_disposable=True`), refuse to run in `production`, and refuse to drop any database not explicitly named `disposable`, `dr_test`, or `dr_demo`.
- Zero data loss is never claimed generically; RPO is measured strictly relative to the captured backup point.

## Running the Drill

```bash
./scripts/demo_disaster_recovery.sh --confirm-disposable
```
