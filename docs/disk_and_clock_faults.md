# Disk and clock faults

Two environment faults the earlier campaigns did not cover, what was found, and what is still open.

## Disk full

`tests/test_disk_full.py` starts a **separate** `postgres:17-alpine` container (the dev databases are
never touched) whose data tablespace is a 16 MB tmpfs, creates a database in it, applies the real
ledger migrations, funds a wallet, fills the tablespace, and keeps posting until the volume refuses to
grow. It skips when Docker or the image is missing.

Observed and asserted:

* every failed posting is `psycopg.errors.DiskFull` (SQLSTATE 53100) and is rolled back;
* reads still work; reconciliation passes; the hash chain verifies; the wallet balance equals the
  number of committed journals times the amount, so nothing is half-applied;
* after space is freed, posting resumes on the same ledger and the chain continues unbroken.

**Bug found and fixed.** `post_journal_entry` (and account status changes) wrapped every database
error as a business `PostingError`, which the funding and cash-out routes return as HTTP 422 with the
raw PostgreSQL message. A full disk, a lock timeout or a shutdown therefore looked like "your request
is invalid", would not be retried by clients, leaked server text, and bypassed the 503 mapping added
with the lock timeouts. `src/ledgerguard/db/errors.py` now classifies infrastructure errors
(SQLSTATE classes 08, 40, 53, 57, 58, `55P03`, and connection errors with no SQLSTATE); they propagate
unwrapped, and the API returns `503` with `Retry-After: 5` and no detail. `55000` (closed account,
immutability) stays a business error.

## Clock faults

| Use | Clock | Under skew |
|---|---|---|
| Journal `created_at`, holds, outbox timestamps | database `NOW()` | One clock; part of each entry hash |
| Hash-chain order and verification | `sequence_number` | Independent of wall time |
| Outbox lease and retry delay | **was the app clock**, now database `NOW() + interval` | Fixed, see below |
| Idempotency wait, rate limiter | monotonic | Immune to wall-clock steps |
| MFA temp token, TOTP, approvals, lockouts, sessions | app wall clock | Not hardened, see limits |
| Reconciliation `run_at`, reports | app wall clock | Informational only |

**Bug found and fixed.** The outbox claim stamped its lease with the worker's `datetime.now()` and
compared it with the database's `NOW()`. A worker clock slower than the database by more than the
lease made the lease expire at once, so another worker re-claimed the event (duplicate delivery; the
inbox makes consumers idempotent, but it is wasted and noisy work); a fast clock stalled retries. The
lease and the failure backoff are now computed in the database, and a test fails if `outbox.py`
imports `datetime` or `time` again.
`tests/test_clock_faults.py` includes a control showing the old failure mode.

## Not covered

* **fsync failure and torn writes** need block-layer fault injection (dm-flakey or similar), which a
  container cannot provide portably. PostgreSQL's own protection (full-page writes, checksums, PANIC on
  fsync failure) is relied on, not tested.
* **WAL volume exhaustion** makes PostgreSQL PANIC and run crash recovery; the test fills only the data
  tablespace. The existing `postgres_crash` scenario covers recovery after a crash.
* **Clock skew in the database host itself** (NTP step backwards) was not injected. Hash-chain checks
  do not depend on time order, but `reconstruct_account_balance_as_of` orders by `created_at` first, so
  a backwards step would make as-of replays follow wall time, not sequence.
* **Application wall-clock expiry** (tokens, approvals, lockouts) was inventoried but not tested under
  skew; separate API instances with different clocks would disagree about expiry by that difference.
