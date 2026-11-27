# Isolation-level study

PostgreSQL 17.11. Every cell is a deterministic two-session interleaving (no timing luck).

`ANOMALY` = invariant violated after both commits; `ABORTED_RETRY_OK` = PostgreSQL raised 40001 and re-running the aborted transaction restored the invariant; `SAFE` = no abort needed.

| Scenario | Mitigation | READ COMMITTED | REPEATABLE READ | SERIALIZABLE |
|---|---|---|---|---|
| lost_update | none | ANOMALY | ABORTED_RETRY_OK | ABORTED_RETRY_OK |
| lost_update | select_for_update | SAFE | ABORTED_RETRY_OK | ABORTED_RETRY_OK |
| lost_update | atomic_update | SAFE | ABORTED_RETRY_OK | ABORTED_RETRY_OK |
| write_skew | none | ANOMALY | ANOMALY | ABORTED_RETRY_OK |
| write_skew | lock_both_rows | SAFE | ABORTED_RETRY_OK | ABORTED_RETRY_OK |
| non_repeatable_read | none | ANOMALY | SAFE | SAFE |
| phantom_read | none | ANOMALY | SAFE | SAFE |

## Real `post_journal` under concurrent overdraft

Concurrent cash-outs against a wallet funded for only some of them, each a whole transaction wrapped in the standard 40001/40P01 retry.

| Level | Workers | Funded for | Succeeded | Rejected (insufficient) | Retries | Final balance | Invariant |
|---|---|---|---|---|---|---|---|
| READ COMMITTED | 8 | 3 | 3 | 5 | 0 | 0 | holds |
| REPEATABLE READ | 8 | 3 | 3 | 5 | 18 | 0 | holds |
| SERIALIZABLE | 8 | 3 | 3 | 5 | 18 | 0 | holds |
