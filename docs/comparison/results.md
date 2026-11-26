# Protocol comparison: TCC vs XA 2PC vs Saga

- Generated: `2026-11-26T09:42:33+00:00` at commit `5e09349b1abab41552b1f568075448b3dfbd0238`
- Environment: {'python': '3.12.13', 'platform': 'macOS-26.7.3-x86_64-i386-64bit', 'postgres': '17.11'}
- Config: ops=48, workers=4, amount=1000 paise

## S1. Throughput and latency (settled transfers only)

| Protocol | Workload | Settled/Ops | TPS | P50 ms | P95 ms |
|---|---|---:|---:|---:|---:|
| TCC | uncontended | 48/48 | 40.16 | 92.91 | 133.55 |
| TCC | hot_source | 48/48 | 40.72 | 94.76 | 119.08 |
| XA-2PC | uncontended | 48/48 | 108.76 | 28.21 | 85.42 |
| XA-2PC | hot_source | 48/48 | 89.19 | 34.06 | 90.38 |
| Saga | uncontended | 48/48 | 252.62 | 15.06 | 16.95 |
| Saga | hot_source | 48/48 | 239.71 | 14.73 | 22.08 |

## S2. Coordinator crash mid-transfer

| Protocol | Crash point | Partial posting visible | Pinned in window | Bystander | Bystander wait ms | Recovery ms | Funds delta after | Clearing delta after | Unresolved after |
|---|---|---|---|---|---:|---:|---:|---:|---:|
| TCC | after durable COMMIT decision, before confirms | False | 1000 paise held as rows (no row locks held) | SETTLED | 49.3 | 26.4 | 0 | 0 | 0 |
| XA-2PC | both legs PREPARED, before COMMIT PREPARED | False | 2 prepared txns holding row locks on both ledgers | BLOCKED | 1507.3 | 88.2 | 0 | 0 | 0 |
| Saga | after step 1 (source debited), before step 2 | True | none (source already debited and committed) | SETTLED | 33.6 | 7.6 | 0 | 0 | 0 |

## S3. Destination rejects the transfer

| Protocol | Final state | Atomic | Customer funds delta | Clearing delta | Journals written |
|---|---|---|---:|---:|---:|
| TCC | CANCELLED | True | 0 | 0 | 0 |
| XA-2PC | CANCELLED | True | 0 | 0 | 0 |
| Saga | CANCELLED | True | 0 | 0 | 2 |
