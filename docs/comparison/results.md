# Protocol comparison: TCC vs XA 2PC vs Saga

- Generated: `2026-11-26T19:03:02+00:00` at commit `648a12afd893a97a5f0cbbe73f70570d68afcad8` (tree `8a7f3b857919b9f10c40cfa460e6464bdd7ae94d`, clean=True)
- Environment: {'python': '3.12.13', 'platform': 'macOS-26.7.3-x86_64-i386-64bit', 'postgres': '17.11', 'cpu_count': '12', 'machine': 'x86_64'}
- Config: ops=48, workers=4, amount=1000 paise

## S1. Throughput and latency (settled transfers only)

Each cell is the mean over `repeats` independent runs (protocols interleaved round-robin, one discarded warm-up run); brackets are 95% Student-t confidence intervals across runs. `ops` per run = 48.

| Protocol | Workload | Runs | Settled/Ops (last run) | TPS mean [95% CI] | TPS sd | P50 ms mean [95% CI] | P95 ms mean [95% CI] |
|---|---|---:|---:|---:|---:|---:|---:|
| TCC | uncontended | 12 | 48/48 | 48.26 [46.51, 50.00] | 2.75 | 80.15 [78.15, 82.16] | 107.6 [85.34, 129.87] |
| TCC | hot_source | 12 | 48/48 | 48.9 [47.10, 50.70] | 2.84 | 79.43 [76.53, 82.32] | 98.97 [89.63, 108.31] |
| XA-2PC | uncontended | 12 | 48/48 | 105.25 [101.05, 109.44] | 6.6 | 29.06 [27.74, 30.38] | 79.23 [71.33, 87.14] |
| XA-2PC | hot_source | 12 | 48/48 | 104.51 [99.27, 109.74] | 8.24 | 28.95 [27.37, 30.52] | 89.76 [79.99, 99.54] |
| Saga | uncontended | 12 | 48/48 | 323.32 [306.84, 339.79] | 25.93 | 11.46 [11.16, 11.76] | 17.43 [10.93, 23.92] |
| Saga | hot_source | 12 | 48/48 | 321.82 [306.79, 336.85] | 23.66 | 11.81 [11.22, 12.41] | 14.69 [13.35, 16.03] |

TPS differences between protocols (non-overlapping 95% CIs):

- uncontended: TCC vs XA-2PC: distinguishable
- uncontended: TCC vs Saga: distinguishable
- uncontended: XA-2PC vs Saga: distinguishable
- hot_source: TCC vs XA-2PC: distinguishable
- hot_source: TCC vs Saga: distinguishable
- hot_source: XA-2PC vs Saga: distinguishable

## S2. Coordinator crash mid-transfer

| Protocol | Crash point | Partial posting visible | Pinned in window | Bystander | Bystander wait ms | Recovery ms | Funds delta after | Clearing delta after | Unresolved after |
|---|---|---|---|---|---:|---:|---:|---:|---:|
| TCC | after durable COMMIT decision, before confirms | False | 1000 paise held as rows (no row locks held) | SETTLED | 57.6 | 34.6 | 0 | 0 | 0 |
| XA-2PC | both legs PREPARED, before COMMIT PREPARED | False | 2 prepared txns holding row locks on both ledgers | BLOCKED | 1507.8 | 41.8 | 0 | 0 | 0 |
| Saga | after step 1 (source debited), before step 2 | True | none (source already debited and committed) | SETTLED | 26.5 | 4.9 | 0 | 0 | 0 |

## S3. Destination rejects the transfer

| Protocol | Final state | Atomic | Customer funds delta | Clearing delta | Journals written |
|---|---|---|---:|---:|---:|
| TCC | CANCELLED | True | 0 | 0 | 0 |
| XA-2PC | CANCELLED | True | 0 | 0 | 0 |
| Saga | CANCELLED | True | 0 | 0 | 2 |
