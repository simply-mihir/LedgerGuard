# LedgerGuard V2 Concurrency & Performance Baseline

- **Generated:** `2026-11-26T06:29:37.234405+00:00`
- **Benchmark schema version:** `2`
- **Source implementation SHA:** `7bb904257e0e9f02fe193a968aa64366f1a1b802`
- **Source tree OID:** `ce065eb818f6a4b6482ca17156cc80943f148768`
- **Source tree clean:** `true`
- **Seed:** `42`
- **Mode:** `smoke` (`workers=[1, 10]`, `warmup_ops=2`, `default_measured_ops=6`, `per_profile_ops={"opposite_direction": 100}`)
- **Environment:** `{"os": "Darwin", "release": "25.6.0", "python": "3.12.13", "cpu_count": 12}`
- **Exact reproduction command:** `uv run python scripts/run_v2_perf_study.py --seed 42 --smoke --opposite-ops 100 --warmup 2 --out-dir docs/performance`

> **Scope Note:** Measurements below reflect controlled local Docker PostgreSQL 17 triad runs and do not claim production bank-scale throughput. Deterministic resource ordering plus bounded transient retry prevented caller-visible failures in the documented PostgreSQL contention campaign.

## Root-Cause Correction: Opposite-Direction Contention

- **Original Failure (`62dc0bd`):** `opposite_direction` at `workers=10`, `measured_ops=6` recorded `failure_count=1`, `error_rate=16.67%`, `deadlocks=1`.
- **Root Cause:** Lock-order inversion inside `source_confirm()` (`migrations/ledger/005_intents_holds_inbox_outbox.sql`) on `account_balances`: `source_confirm` updated the customer wallet row first and then called `post_journal()`, which locked `(CLEARING_ACCOUNT_ID, customer_account_id)` in `account_id ASC` order (`00000000-... < customer_uuid`). Concurrent `destination_confirm()` calls entered `post_journal()` and locked `CLEARING_ACCOUNT_ID` first, forming a 2-transaction deadlock cycle (`SQLSTATE 40P01`).
- **Correction:** Forward migration `migrations/ledger/009_fix_source_confirm_lock_ordering.sql` acquires `FOR UPDATE` on both `account_balances` rows in `ORDER BY account_id ASC` before updating `held_amount_minor`, paired with bounded exponential-backoff retry (`src/ledgerguard/db/retry.py`) for transient PostgreSQL `40P01`/`40001` errors.
- **Verification Workload:** Increased `opposite_direction` to `100` measured operations per worker level (`1` and `10` workers) with `warmup_ops=2` and fixed `seed=42`.

![P95 Latency Comparison](./latency_comparison.svg)

| Profile | Workers | Measured Ops | Success | Fail | Error Rate | Throughput (tps) | P50 (ms) | P95 (ms) | P99 (ms) | Max (ms) | Deadlocks | Deadlock Retries | Ser. Retries | Total Retries |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `uniform_local` | 1 | 6 | 6 | 0 | 0.00% | 127.09 | 7.34 | 8.53 | 8.53 | 8.53 | 0 | 0 | 0 | 0 |
| `uniform_local` | 10 | 6 | 6 | 0 | 0.00% | 140.52 | 16.56 | 40.85 | 40.85 | 40.85 | 0 | 0 | 0 | 0 |
| `uniform_cross_ledger` | 1 | 6 | 6 | 0 | 0.00% | 18.94 | 50.73 | 61.2 | 61.2 | 61.2 | 0 | 0 | 0 | 0 |
| `uniform_cross_ledger` | 10 | 6 | 6 | 0 | 0.00% | 42.56 | 116.7 | 140.54 | 140.54 | 140.54 | 0 | 0 | 0 | 0 |
| `one_hot_account` | 1 | 6 | 6 | 0 | 0.00% | 18.91 | 50.44 | 59.78 | 59.78 | 59.78 | 0 | 0 | 0 | 0 |
| `one_hot_account` | 10 | 6 | 6 | 0 | 0.00% | 41.69 | 116.84 | 143.55 | 143.55 | 143.55 | 0 | 0 | 0 | 0 |
| `ten_hot_accounts` | 1 | 6 | 6 | 0 | 0.00% | 18.49 | 51.48 | 62.89 | 62.89 | 62.89 | 0 | 0 | 0 | 0 |
| `ten_hot_accounts` | 10 | 6 | 6 | 0 | 0.00% | 54.72 | 82.09 | 109.3 | 109.3 | 109.3 | 0 | 0 | 0 | 0 |
| `opposite_direction` | 1 | 100 | 100 | 0 | 0.00% | 16.46 | 52.45 | 101.74 | 154.12 | 223.18 | 0 | 0 | 0 | 0 |
| `opposite_direction` | 10 | 100 | 100 | 0 | 0.00% | 83.26 | 115.15 | 145.04 | 153.84 | 161.02 | 0 | 0 | 0 | 0 |
| `repeated_idempotency` | 1 | 6 | 6 | 0 | 0.00% | 418.91 | 2.19 | 2.99 | 2.99 | 2.99 | 0 | 0 | 0 | 0 |
| `repeated_idempotency` | 10 | 6 | 6 | 0 | 0.00% | 1102.89 | 3.77 | 3.99 | 3.99 | 3.99 | 0 | 0 | 0 | 0 |
| `outbox_backlog` | 1 | 6 | 6 | 0 | 0.00% | 17.74 | 55.44 | 59.0 | 59.0 | 59.0 | 0 | 0 | 0 | 0 |
| `outbox_backlog` | 10 | 6 | 6 | 0 | 0.00% | 60.49 | 86.49 | 97.77 | 97.77 | 97.77 | 0 | 0 | 0 | 0 |
| `recovery_under_load` | 1 | 6 | 6 | 0 | 0.00% | 17.13 | 54.67 | 66.93 | 66.93 | 66.93 | 0 | 0 | 0 | 0 |
| `recovery_under_load` | 10 | 6 | 6 | 0 | 0.00% | 60.12 | 91.34 | 99.03 | 99.03 | 99.03 | 0 | 0 | 0 | 0 |
| `reconciliation_under_load` | 1 | 6 | 6 | 0 | 0.00% | 0.75 | 1260.9 | 1714.17 | 1714.17 | 1714.17 | 0 | 0 | 0 | 0 |
| `reconciliation_under_load` | 10 | 6 | 6 | 0 | 0.00% | 2.59 | 2305.92 | 2317.21 | 2317.21 | 2317.21 | 0 | 0 | 0 | 0 |
| `snapshot_reconstruction` | 1 | 6 | 6 | 0 | 0.00% | 115.87 | 8.46 | 9.96 | 9.96 | 9.96 | 0 | 0 | 0 | 0 |
| `snapshot_reconstruction` | 10 | 6 | 6 | 0 | 0.00% | 324.71 | 14.68 | 17.56 | 17.56 | 17.56 | 0 | 0 | 0 | 0 |
| `journal_hash_verification` | 1 | 6 | 6 | 0 | 0.00% | 66.41 | 13.69 | 21.44 | 21.44 | 21.44 | 0 | 0 | 0 | 0 |
| `journal_hash_verification` | 10 | 6 | 6 | 0 | 0.00% | 102.49 | 44.22 | 57.66 | 57.66 | 57.66 | 0 | 0 | 0 | 0 |
| `approval_workflow` | 1 | 6 | 6 | 0 | 0.00% | 133.92 | 6.57 | 8.96 | 8.96 | 8.96 | 0 | 0 | 0 | 0 |
| `approval_workflow` | 10 | 6 | 6 | 0 | 0.00% | 691.6 | 6.88 | 7.59 | 7.59 | 7.59 | 0 | 0 | 0 | 0 |
