# Protocol comparison: TCC vs XA 2PC vs Saga

- Generated: `2026-11-26T10:53:28+00:00` at commit `98e24278e5d995239275c620acd9eb06ffc6e501` (tree `4368bb6ff4c78501f124cd9a22ed8b72444de520`, clean=True)
- Environment: {'python': '3.12.13', 'platform': 'macOS-26.7.3-x86_64-i386-64bit', 'postgres': '17.11'}
- Config: ops=48, workers=4, amount=1000 paise

## S1. Throughput and latency (settled transfers only)

| Protocol | Workload | Settled/Ops | TPS | P50 ms | P95 ms |
|---|---|---:|---:|---:|---:|
| TCC | uncontended | 48/48 | 41.48 | 87.34 | 135.78 |
| TCC | hot_source | 48/48 | 39.55 | 98.8 | 117.46 |
| XA-2PC | uncontended | 48/48 | 76.39 | 40.63 | 107.16 |
| XA-2PC | hot_source | 48/48 | 92.55 | 31.74 | 82.22 |
| Saga | uncontended | 48/48 | 278.98 | 13.22 | 17.23 |
| Saga | hot_source | 48/48 | 230.68 | 17.14 | 26.01 |

## S2. Coordinator crash mid-transfer

| Protocol | Crash point | Partial posting visible | Pinned in window | Bystander | Bystander wait ms | Recovery ms | Funds delta after | Clearing delta after | Unresolved after |
|---|---|---|---|---|---:|---:|---:|---:|---:|
| TCC | after durable COMMIT decision, before confirms | False | 1000 paise held as rows (no row locks held) | SETTLED | 69.5 | 36.2 | 0 | 0 | 0 |
| XA-2PC | both legs PREPARED, before COMMIT PREPARED | False | 2 prepared txns holding row locks on both ledgers | BLOCKED | 1510.4 | 46.3 | 0 | 0 | 0 |
| Saga | after step 1 (source debited), before step 2 | True | none (source already debited and committed) | SETTLED | 22.7 | 3.6 | 0 | 0 | 0 |

## S3. Destination rejects the transfer

| Protocol | Final state | Atomic | Customer funds delta | Clearing delta | Journals written |
|---|---|---|---:|---:|---:|
| TCC | CANCELLED | True | 0 | 0 | 0 |
| XA-2PC | CANCELLED | True | 0 | 0 | 0 |
| Saga | CANCELLED | True | 0 | 0 | 2 |
