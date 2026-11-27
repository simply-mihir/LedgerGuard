# Index and query-plan study

Evidence: [`docs/query_plans/results.md`](query_plans/results.md) and `results.json`
(regenerate with `uv run python scripts/run_query_plan_report.py` on a clean tree).
Code: `src/ledgerguard/db/query_plans.py`; tests: `tests/test_query_plans.py`,
`tests/test_idempotent_transfer_race.py`; migrations: `migrations/coordinator/010_*`,
`migrations/ledger/011_index_hygiene.sql`.

## Method

A plan on a 20-row development table proves nothing, so each hot query is planned against a
throwaway schema holding *copies* of the real tables (`LIKE ... INCLUDING ALL`, so the real
indexes and CHECKs come along) loaded with 60,000 transfers, 60,000 outbox rows, 100,000 journal
lines and 60,000 holds, then `ANALYZE`d. Production tables are never written. For each of 18
catalogued queries the test asserts the plan contains no sequential scan of the target table and
that the index the planner chose has the same definition as the intended real index. A drift
check fails if the SQL text recorded in the catalogue no longer exists in the source file, and
negative controls drop the index from the scratch copy and show the same query degrading to a
sequential scan, so the assertions are shown able to fail.

Whole-ledger audits (hash-chain verification, full journal balance checks) are O(n) by design and
are intentionally not in the catalogue.

## What it found

1. **A double spend (the important one).** `transfers.idempotency_key` had neither an index nor a
   unique constraint, and the submit path only recorded its idempotency receipt *after*
   settlement. Concurrent requests carrying the same key therefore each inserted and settled
   their own transfer. Reproduced before the fix: 6 concurrent submits of 1,000 from a 10,000
   wallet left it at 4,000 (debited six times) with six `SETTLED` rows for one key.
   *Fix:* migration `coordinator/010` adds `transfer_idempotency_claims` and an `AFTER INSERT`
   trigger on `transfers` that claims the key; a second insert blocks until the first transaction
   ends, then fails with a unique violation. The submit path now inserts-or-adopts
   (`coordinator/idempotent_transfer.py`): the single winner executes the transfer, every other
   request waits for its outcome and returns the same receipt. After the fix the same 6-way race
   gives one transfer, one debit, identical responses and no errors. A key reused with a different
   payload raises `IdempotencyConflictError`. A plain `UNIQUE` index was not used because existing
   rows can already contain duplicates and posted history must not be rewritten: pre-existing keys
   are backfilled to their earliest transfer, legacy duplicates are left untouched and reported as a
   migration notice.
2. **Missing indexes** (coordinator `010`, ledger `011`): the worker's recovery sweep of open
   transfers and the operator "latest transfers" list both scanned the whole `transfers` table;
   historical balance reconstruction scanned released holds; the idempotency lookup scanned
   `transfers`. Added a partial index on unfinished transfers, a `created_at DESC` index, and
   `holds (account_id, created_at)`; the key lookup now uses the claims primary key.
3. **Redundant indexes** (ledger `011`): `idx_journal_lines_account_seq` duplicated
   `uq_account_sequence`, `idx_journal_lines_journal_id` is a prefix of `uq_journal_line`, and
   `idx_transfer_intents_transfer` duplicated a unique constraint. They only add write cost on the
   hottest write path, so they were dropped; a test now fails if any database regains one.

## Limits

* The plans are for synthetic data of the stated size on one PostgreSQL 17 instance. Row
  distributions (for example 1 in 200 transfers open) are assumptions, not production figures.
* Dropping redundant indexes should reduce write cost; I did not benchmark it.
* The claims-table fix removes the duplicate execution, but an adopting request waits at most 15 s
  for the owner and then returns the transfer's current state; the client can retry with the same
  key and the recovery sweep keeps driving the transfer.
* Existing dev databases can already hold legacy duplicates from before the fix (this repository's
  own did, from the reproduction). They are historical rows and were not altered.
* Execution time was not part of the assertions; only the plan shape was.
