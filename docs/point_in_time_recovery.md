# Point-in-time recovery (PITR)

`docs/disaster_recovery.md` covers logical dump/restore. A dump only returns the ledger to the moment it
was taken; everything since is lost. PITR closes that gap: a physical base backup plus continuously
archived WAL lets the database be rebuilt to *any* named moment, such as just before an operator error.

## The drill (`src/ledgerguard/dr/pitr.py`, `scripts/run_pitr_drill.py`)

On a throwaway `postgres:17-alpine` with `archive_mode=on` (the dev databases are never touched):

1. apply the real ledger migrations, take `pg_basebackup`;
2. post real ledger activity (accounts and fundings) - these exist only in archived WAL;
3. `pg_create_restore_point('before_disaster')`;
4. simulate an operator error (`DROP TABLE journal_lines CASCADE`) and one more committed write;
5. start a second instance from the base backup with `recovery_target_name = 'before_disaster'`.

Result (`docs/pitr/results.json`, asserted by `tests/test_pitr.py`): the primary really lost
`journal_lines`; the recovered instance has all 5 post-backup journals, does not contain the later
write, and its journal hash chain verifies end to end.

## What it does not cover

Archiving to remote or durable storage (the drill archives to tmpfs inside the container), archive
retention and expiry, backup encryption, recovery time at production volume, and enabling
`archive_mode` on the dev/production compose stack (it is off there: archiving without a retention and
monitoring plan fills disks). Turning it on is an operational decision; this drill shows the procedure
works and what a runbook must contain.
