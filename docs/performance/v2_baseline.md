# LedgerGuard V2 Concurrency & Performance Baseline

- **Generated:** `2026-11-26T05:01:44.672628+00:00`
- **Git SHA:** `62dc0bd`
- **Seed:** `42`
- **Environment:** `{"os": "Darwin", "release": "25.6.0", "python": "3.12.13", "cpu_count": 12}`
- **Reproduce Command:** `uv run python scripts/run_v2_perf_study.py --seed 42`

> **Scope Note:** Measurements below reflect controlled local Docker PostgreSQL 17 triad runs and do not claim production bank-scale throughput.

![P95 Latency Comparison](./latency_comparison.svg)

| Profile | Workers | Measured Ops | Success | Fail | Error Rate | Throughput (tps) | P50 (ms) | P95 (ms) | P99 (ms) | Max (ms) | Deadlocks |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `uniform_local` | 1 | 6 | 6 | 0 | 0.00% | 103.06 | 9.37 | 11.52 | 11.52 | 11.52 | 0 |
| `uniform_local` | 10 | 6 | 6 | 0 | 0.00% | 126.45 | 21.6 | 46.39 | 46.39 | 46.39 | 0 |
| `uniform_cross_ledger` | 1 | 6 | 6 | 0 | 0.00% | 14.83 | 64.09 | 77.12 | 77.12 | 77.12 | 0 |
| `uniform_cross_ledger` | 10 | 6 | 6 | 0 | 0.00% | 35.73 | 145.32 | 166.86 | 166.86 | 166.86 | 0 |
| `one_hot_account` | 1 | 6 | 6 | 0 | 0.00% | 15.78 | 51.56 | 99.83 | 99.83 | 99.83 | 0 |
| `one_hot_account` | 10 | 6 | 6 | 0 | 0.00% | 51.17 | 89.66 | 116.45 | 116.45 | 116.45 | 0 |
| `ten_hot_accounts` | 1 | 6 | 6 | 0 | 0.00% | 16.07 | 60.91 | 64.63 | 64.63 | 64.63 | 0 |
| `ten_hot_accounts` | 10 | 6 | 6 | 0 | 0.00% | 49.78 | 104.14 | 120.13 | 120.13 | 120.13 | 0 |
| `opposite_direction` | 1 | 6 | 6 | 0 | 0.00% | 15.25 | 64.92 | 73.61 | 73.61 | 73.61 | 0 |
| `opposite_direction` | 10 | 6 | 5 | 1 | 16.67% | 5.45 | 1083.68 | 1098.8 | 1098.8 | 1098.8 | 1 |
| `repeated_idempotency` | 1 | 6 | 6 | 0 | 0.00% | 364.32 | 2.66 | 2.95 | 2.95 | 2.95 | 0 |
| `repeated_idempotency` | 10 | 6 | 6 | 0 | 0.00% | 826.17 | 4.58 | 5.37 | 5.37 | 5.37 | 0 |
| `outbox_backlog` | 1 | 6 | 6 | 0 | 0.00% | 14.4 | 68.49 | 75.84 | 75.84 | 75.84 | 0 |
| `outbox_backlog` | 10 | 6 | 6 | 0 | 0.00% | 50.28 | 109.72 | 116.42 | 116.42 | 116.42 | 0 |
| `recovery_under_load` | 1 | 6 | 6 | 0 | 0.00% | 17.97 | 54.55 | 57.78 | 57.78 | 57.78 | 0 |
| `recovery_under_load` | 10 | 6 | 6 | 0 | 0.00% | 49.52 | 112.4 | 118.38 | 118.38 | 118.38 | 0 |
| `reconciliation_under_load` | 1 | 6 | 6 | 0 | 0.00% | 0.42 | 2382.04 | 2430.34 | 2430.34 | 2430.34 | 0 |
| `reconciliation_under_load` | 10 | 6 | 6 | 0 | 0.00% | 1.41 | 4223.72 | 4240.25 | 4240.25 | 4240.25 | 0 |
| `snapshot_reconstruction` | 1 | 6 | 6 | 0 | 0.00% | 122.42 | 7.9 | 10.19 | 10.19 | 10.19 | 0 |
| `snapshot_reconstruction` | 10 | 6 | 6 | 0 | 0.00% | 512.22 | 9.69 | 10.42 | 10.42 | 10.42 | 0 |
| `journal_hash_verification` | 1 | 6 | 6 | 0 | 0.00% | 34.99 | 24.37 | 40.27 | 40.27 | 40.27 | 0 |
| `journal_hash_verification` | 10 | 6 | 6 | 0 | 0.00% | 53.26 | 82.42 | 111.15 | 111.15 | 111.15 | 0 |
| `approval_workflow` | 1 | 6 | 6 | 0 | 0.00% | 186.89 | 5.37 | 6.83 | 6.83 | 6.83 | 0 |
| `approval_workflow` | 10 | 6 | 6 | 0 | 0.00% | 459.5 | 11.01 | 12.05 | 12.05 | 12.05 | 0 |
