# Protocol comparison: TCC vs XA two-phase commit vs Saga

**Question.** LedgerGuard moves money between independent PostgreSQL ledgers with
Try-Confirm-Cancel (TCC) and a durable coordinator decision (see
[ADR 0002](adr/0002-tcc-and-forward-recovery.md)). What does that buy compared with the two
usual alternatives, and what does it cost?

**Answer, measured.** TCC is the *slowest* protocol on the happy path, and the only one of
the three that is simultaneously **non-blocking** and **free of exposed partial state** when
the coordinator crashes at its most vulnerable moment, while writing **no journals** for a
transfer that the destination rejects.

## Method

All three protocols post the *same* balanced journals through the *same* `post_journal`
stored function on the *same* two PostgreSQL 17 ledgers, using the same pooled connections.
Only the commit protocol differs.

| Protocol | Implementation |
|---|---|
| **TCC** | LedgerGuard's production path: holds, durable COMMIT/CANCEL decision, inbox/outbox, forward recovery. |
| **XA-2PC** | `PREPARE TRANSACTION` on both ledgers, then `COMMIT PREPARED` (psycopg two-phase API). Row locks are held by the prepared transaction until resolved. |
| **Saga** | Commit the source debit, then commit the destination credit; a failing second step runs a compensating journal. No isolation between steps. |

Scenarios (`src/ledgerguard/comparison/scenarios.py`):

* **S1 Throughput.** `ops` transfers over `workers` threads, uncontended (one account pair
  per worker) and `hot_source` (all workers debit one account).
* **S2 Coordinator crash.** Crash at each protocol's most vulnerable point (table below),
  then (a) inspect balances, (b) attempt a *bystander* transfer from the same source with a
  bounded lock wait, (c) run the protocol's recovery, (d) check conservation.
* **S3 Destination rejects.** The destination account is closed. We measure whether the
  outcome is atomic and how many journals were written for the failed transfer.

| Protocol | Crash point used in S2 |
|---|---|
| TCC | after the durable COMMIT decision, before any confirm |
| XA-2PC | both legs PREPARED, before `COMMIT PREPARED` |
| Saga | after step 1 (source debited and committed), before step 2 |

Reproduce:

```bash
docker compose -f docker-compose.yml -f docker-compose.xa.yml up -d   # ledgers get max_prepared_transactions=64 (XA baseline only)
uv run python scripts/run_protocol_comparison.py --ops 48 --workers 4
```

Tests with hard assertions on every claim below: `tests/test_protocol_comparison.py`.

## Results

Committed evidence: [`docs/comparison/results.md`](comparison/results.md) and
[`results.json`](comparison/results.json) (run on one developer machine, local Docker).

| Property | TCC | XA-2PC | Saga |
|---|---|---|---|
| Happy-path throughput (4 workers) | ~40 TPS | ~90-110 TPS | ~240-250 TPS |
| Row locks pinned while coordinator is down | **none** (a hold is an ordinary row) | **yes** (prepared txns on both ledgers) | none |
| Unrelated transfer on the same source during the outage | **succeeds (~50 ms)** | **blocked** until lock timeout (1.5 s here; unbounded without one) | succeeds |
| Partially applied transfer visible in posted balances | **no** | no | **yes** (source already debited) |
| Journals written for a transfer the destination rejects | **0** | **0** | **2** (debit + compensation) |
| Funds conserved and nothing unresolved after recovery | yes | yes | yes |

### Reading the numbers honestly

* **TCC pays for its guarantees.** Each transfer performs several short local transactions
  plus coordinator writes (decision, workflow events, outbox/inbox). XA does two prepares and
  two commits; a Saga does two commits. Expect TCC throughput well below both here.
* **XA's problem is not speed, it is blocking.** Any transaction that needs a row locked by a
  prepared transaction waits for the coordinator. Throughput numbers do not show this; S2 does.
* **Saga is fastest and weakest.** Between steps the debit is committed and visible, and a
  failed transfer permanently adds a debit and a compensating credit to immutable history.
* The hold-based design means a TCC bystander is bounded by *available* balance, not by locks.

## Limitations and threats to validity

* One machine, two Postgres containers on loopback: network latency is near zero, which
  favours protocols with fewer local round trips. Absolute numbers are not production capacity.
* The XA and Saga baselines are minimal. Their "coordinator log" is in-process state that
  stands in for a durable log, so they have no coordinator-crash recovery of their own beyond
  the re-drive shown in S2. A production XA manager would add that, at extra cost.
* S2 measures one crash point per protocol, chosen as the most harmful for that protocol.
  Other crash points have different (usually milder) effects.
* Small sample sizes (default 48 operations per workload); latencies are indicative, not
  statistically tight. Re-run with larger `--ops` and report medians.
* Single bystander transfer; a lock-wait bound of 1.5 s truncates XA's true blocked time.
* The comparison does not claim TCC is better in general; it shows the trade-off for this
  workload (funds movement between independent ledgers where partial state must not leak).
