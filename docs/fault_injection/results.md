# Real fault-injection campaign

- Generated `2026-11-26T21:38:07+00:00` at commit `99b82d32b41beb90c1c19dc4aec50f0c2bf6ce37` (tree `22426e34c8f8d1b1bfcfeaad6c82f64ca0ef7eee`, clean=True), seed `42`
- Environment: {'python': '3.12.13', 'platform': 'macOS-26.7.3-x86_64-i386-64bit', 'postgres': '17.11'}
- **Overall: PASS**

| Scenario | Faults injected | Transfers | Settled | Cancelled | Recovered | Invariants | Key facts |
|---|---|---:|---:|---:|---:|---|---|
| SIGKILL after durable COMMIT | kill -9 worker, ledger-1 +120ms | 4 | 4 | 0 | 4 | 9/9 PASS | kills_inside_commit_window=4/4 |
| Random SIGKILL burst | kill -9 x4 (seeded) | 9 | 9 | 0 | 2 | 9/9 PASS | worker_kills=4 |
| Network latency | ledger-1 +150ms, ledger-2 +150ms | 8 | 8 | 0 | 0 | 9/9 PASS | worker_finished=True; done_events=8 |
| Partition of destination ledger | ledger-2 black-hole, kill -9 hung worker | 3 | 3 | 0 | 1 | 9/9 PASS | progress_during_partition=0; bytes_dropped_by_partition=6 |
| TCP reset storm | RST on live connections, random link | 11 | 11 | 0 | 1 | 9/9 PASS | connections_reset=28; worker_errors=2 |
| Byte corruption | bit flips in 15% of chunks | 2 | 2 | 0 | 0 | 9/9 PASS | clean_transfers_before_damage=2; worker_finished_under_fault=False; chunks_or_streams_damaged=1; seed=42 |
| Chunk reorder + duplicate | 20% adjacent-chunk swaps, 10% duplicated chunks | 2 | 2 | 0 | 0 | 9/9 PASS | clean_transfers_before_damage=2; worker_finished_under_fault=False; chunks_or_streams_damaged=1; seed=42 |
| Mid-message truncation | stream cut + RST after 1.5 KB | 6 | 6 | 0 | 4 | 9/9 PASS | clean_transfers_before_damage=2; worker_finished_under_fault=True; chunks_or_streams_damaged=13; seed=42 |
| API SIGKILL + idempotent replay | kill -9 API mid-burst, client retries | 30 | 30 | 0 | 0 | 5/5 PASS | acked_before_crash=19; unacked_replayed=11 |
| PostgreSQL SIGKILL (postgres-ledger2) | docker kill -s KILL postgres-ledger2, restart | 12 | 12 | 0 | 0 | 9/9 PASS | container_killed=postgres-ledger2; worker_survived_outage=True |
| PostgreSQL SIGKILL (postgres-coordinator) | docker kill -s KILL postgres-coordinator, restart | 11 | 11 | 0 | 0 | 9/9 PASS | container_killed=postgres-coordinator; worker_survived_outage=True |

## Invariants checked after recovery (every scenario)

- `all_transfers_terminal`
- `customer_funds_conserved`
- `clearing_nets_to_zero`
- `no_orphaned_holds`
- `single_settlement_per_transfer`
- `decision_never_reverted`
- `cross_ledger_reconciliation`
- `journal_hash_chains_intact`
- `histories_conform_to_tla_spec`
- `every_key_succeeds_on_replay`
- `replay_returns_same_transfer`
- `each_key_applied_exactly_once`
- `acknowledged_transfers_preserved`
- `ledger_reconciliation`
