# Chaos Testing in LedgerGuard V2

## Overview

LedgerGuard V2 includes a deterministic chaos campaign engine (`src/ledgerguard/chaos/`) that exercises concurrent local and cross-ledger TCC transfers while injecting crashes, lost replies, duplicate deliveries, out-of-order cancellations, artificial delays, and hot-account contention.

## Supported Faults (18 Modes)

1. `COORDINATOR_CRASH_BEFORE_SOURCE_PREPARE`
2. `COORDINATOR_CRASH_AFTER_SOURCE_PREPARE`
3. `COORDINATOR_CRASH_AFTER_DEST_PREPARE`
4. `COORDINATOR_CRASH_AFTER_COMMIT`
5. `COORDINATOR_CRASH_BETWEEN_CONFIRMS`
6. `SOURCE_PARTICIPANT_UNAVAILABLE`
7. `DEST_PARTICIPANT_UNAVAILABLE`
8. `OUTBOX_WORKER_CRASH`
9. `RECOVERY_WORKER_CRASH`
10. `DUPLICATE_COMMAND_DELIVERY`
11. `REORDERED_COMMAND_DELIVERY`
12. `LOST_REPLY_AFTER_PARTICIPANT_COMMIT`
13. `TEMP_DB_CONNECTION_FAILURE`
14. `POSTGRES_PARTICIPANT_RESTART`
15. `CLIENT_RETRY_STORM`
16. `HOT_ACCOUNT_CONTENTION`
17. `ARTIFICIAL_PROCESSING_DELAY`
18. `EXHAUSTED_RETRY_BUDGET`

## Running a Campaign

```bash
uv run python scripts/run_chaos_campaign.py --seed 42 --ops 24 --workers 4 --output chaos_report.json
```

## Safety & Environment Guards

- Chaos endpoints (`/v1/operator/chaos/run`) and `ChaosCampaignEngine.run()` reject execution with `403 Forbidden` / `RuntimeError` when `LEDGERGUARD_ENV=production`.
- Incomplete cluster reachability (`coverage != "FULL"`) never reports `PASS`; it reports `INCOMPLETE` per invariant `I14`.
