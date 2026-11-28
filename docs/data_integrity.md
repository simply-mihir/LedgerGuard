# Database-enforced state machines, page checksums and storage tuning

Three hardening items taken from the pre-refinement audit. Each is a forward migration or
configuration change; no journal, hold, intent or transfer row is read, rewritten or moved.

## 1. State machines in the database

Before this change the legal transitions of a transfer, hold, intent or account lived only in
application code, and the runtime role may `UPDATE` those rows. The database now refuses an illegal
transition itself (`coordinator/011`, `ledger/013`).

| Table | Rule enforced by trigger |
|---|---|
| `transfers` | Created only as `ACCEPTED`. State moves only along `transfer_state_transitions`: `ACCEPTED`/`PREPARING` to a decided or `REJECTED` state, `COMMITTING` to `SETTLED`, `CANCELLING` to `CANCELLED`; terminal states never leave. `COMMITTING`/`SETTLED` require a durable `COMMIT` decision and `CANCELLING`/`CANCELLED` a durable `CANCEL` decision (the TLA+ commit/cancel exclusivity, in SQL). |
| `transfer_decisions` | A durable decision can never be updated (decision monotonicity). |
| `holds` | Created `ACTIVE`; only `ACTIVE` to `CONSUMED` or `RELEASED`; account, transfer and amount immutable. |
| `transfer_intents` | Created `PREPARED` (or `CANCELLED`, the cancel-before-prepare tombstone); only `PREPARED` to `CONFIRMED`/`CANCELLED`; direction, accounts, amount and currency immutable. |
| `ledger_accounts` | `CLOSED` is terminal; type, normal side and currency immutable. |

An update that does not change the state (an attention flag, a refunded amount) is unaffected.
Violations raise SQLSTATE `55000`, which the API already treats as a business error, not an
infrastructure failure.

Evidence (`tests/test_state_machine_triggers.py`, 75 tests, every attempt rolled back): the full 7 x 7
transfer transition matrix is checked against the expected set, including decision linkage; hold and
intent matrices; every immutable column; creation in a later state; decision flip.

**Finding while adding it.** Two existing tests built their scenario by inserting a transfer
directly as `COMMITTING` / `SETTLED`, a state the system can only reach through a decision. They now
reach it the legal way, with their assertions unchanged. The participant conformance tamper tests
now come in two halves: the ledger refuses the edit, and when the triggers are bypassed
(`session_replication_role = replica`, simulating a bad restore or a disabled trigger) conformance
still detects it. The checker stays valuable as the second line of defence.

Limits: a superuser can disable triggers; these protect against application bugs and ordinary roles,
not against a hostile database owner. The transition table is owner-managed (the runtime role has
only `SELECT`).

## 2. Data checksums

The three PostgreSQL 17 containers were initialised without page checksums, so a flipped bit in a data
file was returned to the application as valid data. `docker-compose.yml` now sets
`POSTGRES_INITDB_ARGS: "--data-checksums"`.

Evidence (`tests/test_data_checksums.py`): two throwaway containers, identical except for the flag. A
table is written and checkpointed, four bytes inside a tuple are overwritten in the data file, and
the server is restarted to empty its buffers. With checksums the read fails with `XX001 invalid page
in block 0` (the detail names the checksum mismatch). Without them the query succeeds and returns the
damaged value. A second test asserts all three compose services carry the flag.

Limits and operations:

* Compose enables it at `initdb`, so it applies to **new volumes** (CI always creates fresh ones). The
  maintainer's three existing development volumes were converted offline with `pg_checksums --enable` after
  a clean stop; `tests/test_data_checksums.py` asserts the running databases report `data_checksums = on`
  with zero failures. Any other pre-existing volume needs the same conversion (or recreation).
* Checksums **detect** corruption on read; they do not repair it, and a page that is never read is
  never checked. Backups and `pg_checksums --check` (offline) or `pg_amcheck` find the rest.
* This exercises corruption of an on-disk page, not fsync failure or torn writes (still untested).

## 3. Storage tuning

Metadata-only `ALTER TABLE ... SET (...)`; existing pages are not rewritten.

* **Fillfactor 90** on `account_balances`, `transfer_intents` and `transfers`, which are updated
  repeatedly per row. Measured on an `account_balances`-shaped scratch table (20,000 random
  single-row updates): default fillfactor gave 96.9% HOT updates; 90 gave 100%, at a smaller size than
  fillfactor 80 (237,568 vs 262,144 bytes; default 245,760). A first attempt at 80 was rejected for
  being larger without being faster. `tests/test_storage_tuning.py` re-measures this.
* **Autovacuum on dead tuples** (`scale_factor` 0.02 to 0.05 plus a threshold of 50) on the hot-update
  tables and the outboxes, instead of waiting for 20% of the table. `journal_chain_head` (a single row
  written on every commit) is vacuumed on a fixed threshold.
* **Journals are untouched.** `journal_headers`, `journal_lines`, snapshots and audit tables are
  insert-only, so full pages are correct; a test asserts they keep the default fillfactor.

What the live statistics showed, and why some tables get no fillfactor: `transfers` only had 52% HOT
updates and `holds` and `outbox_events` 0%, because their updated columns are indexed (`transfers.state`
is the predicate of the partial index `idx_transfers_open_created`; `holds.status` of
`idx_holds_account_active`; `outbox_events.next_attempt_at` of `idx_outbox_pending`). Those updates
can never be HOT whatever the fillfactor, so only vacuum helps and only vacuum is tuned. This is a
deliberate trade: those partial indexes make the open-transfer, active-hold and pending-outbox scans
cheap.

Limits: the values come from a synthetic single-instance measurement and reasoning, not a production
workload; autovacuum thresholds should be revisited against `pg_stat_user_tables` once real traffic
exists (`n_dead_tup`, `n_tup_hot_upd`).
