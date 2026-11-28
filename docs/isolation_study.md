# Isolation-level study

Evidence: [`docs/isolation/results.md`](isolation/results.md) and `results.json`
(regenerate with `uv run python scripts/run_isolation_study.py` on a clean tree).
Code: `src/ledgerguard/isolation/study.py`; tests: `tests/test_isolation_study.py`.

## Method

Real PostgreSQL sessions are interleaved **step by step from one script**, so every anomaly
reproduces the same way every run. Where a statement must queue behind a row lock, it runs on a
second thread and the harness waits until `pg_stat_activity` shows that backend in a `Lock` wait
before releasing the holder. There are no sleeps standing in for ordering.

Textbook anomalies run in a throwaway schema that is dropped afterwards. The last scenario drives
the real `post_journal` function. Amounts are integer minor units.

Outcomes: `ANOMALY` (invariant violated after both commits), `ABORTED_RETRY_OK` (PostgreSQL
raised SQLSTATE 40001 and re-running the whole aborted transaction restored the invariant) and
`SAFE`.

## Result (PostgreSQL 17)

| Scenario | Mitigation | READ COMMITTED | REPEATABLE READ | SERIALIZABLE |
|---|---|---|---|---|
| lost update | none (read, compute in app, write) | **ANOMALY** | abort + retry | abort + retry |
| lost update | `SELECT ... FOR UPDATE` | safe | abort + retry | abort + retry |
| lost update | atomic `SET bal = bal - x` | safe | abort + retry | abort + retry |
| write skew | none | **ANOMALY** | **ANOMALY** | abort + retry |
| write skew | lock every row the rule reads | safe | abort + retry | abort + retry |
| non-repeatable read | none | **ANOMALY** | safe | safe |
| phantom read | none | **ANOMALY** | safe | safe |

Two points worth stating plainly:

* **REPEATABLE READ does not stop write skew.** Two sessions that read the same joint total and
  write *different* rows see no write-write conflict. Only SERIALIZABLE (SSI) or locking every
  row the rule reads prevents it.
* **READ COMMITTED is safe only if the code takes locks or uses atomic updates.** Unlocked
  read-modify-write loses an update there (a 30 and a 50 withdrawal from 100 left 50, not 20).

## What this means for LedgerGuard

`post_journal` locks every touched `account_balances` row `FOR UPDATE` in ascending account order
before reading balances. With 8 concurrent cash-outs against a wallet funded for 3, exactly 3
succeed, 5 are rejected for insufficient funds and the balance ends at 0 **at all three isolation
levels**. At READ COMMITTED this needs **zero retries**; REPEATABLE READ and SERIALIZABLE reach
the same result only after repeated 40001 aborts retried by `run_with_transient_retry`. The
existing design (explicit ordered row locks at the default level) is therefore the cheaper correct
choice, and the retry wrapper is what makes the stricter levels usable if ever required.

The per-account balance rule is a single-row invariant, so write skew does not apply to
`post_journal` itself. Any future rule that spans several rows (a per-customer total limit, say)
must either lock all rows it reads or run at SERIALIZABLE with retry, because REPEATABLE READ
would silently allow the anomaly above.

## Limits

* One PostgreSQL version (17.11) and one machine; the matrix is PostgreSQL's behaviour, not a
  general statement about other engines (PostgreSQL treats READ UNCOMMITTED as READ COMMITTED
  and has no dirty reads, so that level is not studied).
* The real-system scenario uses 8 workers on a single wallet. It shows safety and retry cost
  qualitatively; the retry counts are not a benchmark and are not asserted at the stricter levels.
* The study does not change production behaviour: no isolation level was altered anywhere in
  the application.
