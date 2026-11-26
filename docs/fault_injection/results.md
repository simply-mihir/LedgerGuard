# Real fault-injection campaign

- Generated `2026-11-26T10:25:52+00:00` at commit `4be92b359f835ee169d4d00baa01f8078578330a`, seed `42`
- Environment: {'python': '3.12.13', 'platform': 'macOS-26.7.3-x86_64-i386-64bit', 'postgres': '17.11'}
- **Overall: PASS**

| Scenario | Faults injected | Transfers | Settled | Cancelled | Recovered | Invariants | Key facts |
|---|---|---:|---:|---:|---:|---|---|
| SIGKILL after durable COMMIT | kill -9 worker, ledger-1 +120ms | 4 | 4 | 0 | 5 | 9/9 PASS | kills_inside_commit_window=4/4 |
| Random SIGKILL burst | kill -9 x4 (seeded) | 13 | 13 | 0 | 2 | 9/9 PASS | worker_kills=4 |
| Network latency | ledger-1 +150ms, ledger-2 +150ms | 8 | 8 | 0 | 0 | 9/9 PASS | worker_finished=True; done_events=8 |
| Partition of destination ledger | ledger-2 black-hole, kill -9 hung worker | 3 | 3 | 0 | 1 | 9/9 PASS | progress_during_partition=0; bytes_dropped_by_partition=11 |
| TCP reset storm | RST on live connections, random link | 6 | 6 | 0 | 3 | 9/9 PASS | connections_reset=18; worker_errors=9 |
| API SIGKILL + idempotent replay | kill -9 API mid-burst, client retries | 30 | 30 | 0 | 0 | 5/5 PASS | acked_before_crash=19; unacked_replayed=11 |
| PostgreSQL SIGKILL (postgres-ledger2) | docker kill -s KILL postgres-ledger2, restart | 12 | 12 | 0 | 3 | 9/9 PASS | container_killed=postgres-ledger2; worker_survived_outage=True |
| PostgreSQL SIGKILL (postgres-coordinator) | docker kill -s KILL postgres-coordinator, restart | 10 | 10 | 0 | 1 | 9/9 PASS | container_killed=postgres-coordinator; worker_survived_outage=True |

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
