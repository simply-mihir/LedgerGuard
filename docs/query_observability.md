# Query observability, reporting views and outbox wake-ups

## pg_stat_statements
Compose preloads `pg_stat_statements` on all three databases (`shared_preload_libraries`, also in the XA
overlay). `ledgerguard.db.query_stats` creates the extension on demand (admin only; not in a migration so
a server without the preload cannot break migration) and `scripts/top_statements.py [limit]` prints the
costliest statements per database. Existing containers need `docker compose up -d` once to pick up the
setting. Limit: statistics are in shared memory and reset on restart; nothing exports them yet.

## Reporting views (`ledger/014`, `coordinator/012`)
`v_trial_balance`, `v_account_balances`, `v_transfer_state_summary`, `v_open_transfers` give the reporter
role one database-side definition of balances and open work. All are `security_invoker`, so the reader's
own privileges and row-level-security apply; the reporter has SELECT only. Tests compare the views with the
raw lines and with the ledger's `account_balances`.

## Outbox LISTEN/NOTIFY and the recovery worker (`coordinator/013`, `worker/outbox.py`, `worker/daemon.py`)
A statement-level trigger issues `pg_notify('outbox_ready')` on insert. NOTIFY is transactional, so a
rolled-back enqueue never wakes anyone. The notification is a hint only. `uv run python -m ledgerguard.cli
run-worker` runs the always-on worker: it holds one LISTEN connection (`OutboxListener`), lets new work age past
`min_age_seconds` (so it does not race a request still executing inline), then runs the idempotent recovery
sweep; the same sweep also runs on a poll timer, so correctness never depends on a notification (they are lost
when nobody listens or the server restarts). The sweep is a cluster-wide singleton (advisory lock). Only
classified transient database failures are retried; anything else stops the worker.
`tests/test_worker_daemon.py` shows a crashed cross-ledger transfer recovered to SETTLED within seconds with a
60 s poll interval, i.e. woken by NOTIFY, and with exactly one debit.
