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

## Outbox LISTEN/NOTIFY (`coordinator/013`, `worker.outbox.wait_for_outbox_work`)
A statement-level trigger issues `pg_notify('outbox_ready')` on insert. NOTIFY is transactional, so a
rolled-back enqueue never wakes anyone. The notification is a hint only: consumers still claim work with
`FOR UPDATE SKIP LOCKED` and must keep a timed poll as fallback, since notifications are lost when nobody
listens or the server restarts. Honest scope: the repository has no always-on outbox consumer loop (the
workflow drives claims directly), so this provides and tests the wake-up primitive; it is not yet wired
into a daemon.
