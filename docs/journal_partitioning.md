# Journal partitioning: decision and evidence

**Decision: `journal_headers` and `journal_lines` are not natively partitioned.** The study in
`src/ledgerguard/db/partition_study.py` (run with `scripts/run_partition_study.py`, output in
`docs/partitioning/`) shows that every native layout either weakens a database-enforced ledger
invariant or makes the hot path slower. Nothing in the real schema changed.

## Why not

| Finding | What was measured |
|---|---|
| Unique keys must contain the partition key | On a table partitioned by `created_at`, PostgreSQL refuses `PRIMARY KEY (journal_id)` and `UNIQUE (sequence_number)` (0A000), and refuses an FK from `journal_lines` to `journal_id` (42830). |
| The accepted layout loses global uniqueness | With `(journal_id, created_at)` and `(sequence_number, created_at)`, a duplicate `journal_id` or `sequence_number` in a different partition is accepted. The unpartitioned table rejects both with 23505. The hash chain's "one entry per sequence number" rule would then rest on the chain-head lock and the verifier, not the database. |
| Partitioning by sequence number is not possible | `sequence_number` is assigned by the deferred sealing trigger after the insert, so the row has no partition key when it is inserted. Assigning it earlier would hold the chain-head lock for the whole transaction. |
| Hash-partitioning lines keeps one key, loses the rest | `HASH (account_id)` preserves `UNIQUE (account_id, account_sequence)`, but not `UNIQUE (journal_id, line_no)`. Lookups by `journal_id`, which the balanced-journal trigger and the sealer run on every posting, probe all 8 partitions instead of 1. Account lookups prune to 1. |
| Partition drop is a new way to erase history | `DELETE` and `TRUNCATE` are blocked by the immutability triggers, but `DETACH PARTITION` and `DROP` of a partition fire neither and remove rows. Only privileges would stand in the way. |

The usual reason to partition, retiring old data, also conflicts with a ledger that never deletes
posted history and verifies a chain from sequence 1.

## What covers the same needs today

* Time-range and account reads use indexes (`docs/query_plans.md`); the journals are append-only and
  small per row, so index depth grows logarithmically.
* Chain verification can resume from a `journal_checkpoints` Merkle checkpoint rather than from the
  start.
* Backups and long-term storage are a PITR/WAL concern, not a table-layout one.

## Revisit when

A single ledger database passes the size where index maintenance or `VACUUM` of the journals is
measurably the bottleneck. A safe design would first need: a global sequence/journal-id uniqueness
mechanism that is database-enforced (for example a narrow, unpartitioned registry table written by the
sealing trigger), an event trigger or privilege model that blocks `DROP`/`DETACH` of journal
partitions, and a forward migration that copies rather than mutates history. The test
`tests/test_journal_partitioning.py` fails if the journals are partitioned without those answers.

## Limits of this study

It runs on one PostgreSQL 17 instance with small synthetic tables; it measures constraint behaviour
and which partitions a plan touches, not throughput. It does not prove that no partitioning scheme
exists, only that none of the native layouts tried keeps every invariant.
