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

## WAL exhaustion, clock steps and application clocks

* **WAL volume exhaustion** (`faults/wal_full.py`, `tests/test_wal_full.py`): `pg_wal` on a 48 MB tmpfs with
  archiving failing. Writes fail with SQLSTATE 53100 `could not write to file pg_wal/...`, classified as an
  infrastructure failure (HTTP 503), and the server then stops because PostgreSQL cannot continue without
  WAL space. Restart recovery after exhaustion is *not* examined: a tmpfs is erased when the container stops.
* **Database-host clock steps**: `reconstruct_account_balance_as_of` now treats "as of T" as a *prefix* of the
  account's sequence (`history.reconstruction.select_as_of_prefix`); a backwards step can no longer yield a
  balance that never existed. The step itself cannot be injected into a container without moving the host's
  clock, so the rule is tested with synthetic non-monotonic timestamps.
* **Application wall clocks**: sessions (creation, absolute and idle expiry), login and MFA lockouts,
  enrollment expiry and approval expiry are all measured by the database clock
  (`tests/test_auth_clock_skew.py`, `tests/test_clock_faults.py`: sessions stay valid with the process clock
  set ten years either way). Two mechanisms are inherently wall-clock and are tested for tolerance instead:
  TOTP codes (RFC 6238, fixed drift window) and the signed five-minute MFA temp token (tolerates two minutes
  of skew, fails closed at an hour).

## Not covered

* **fsync failure and torn writes** need block-layer fault injection (dm-flakey or similar), which a container
  cannot provide portably. PostgreSQL's own protection (full-page writes, page checksums, PANIC on fsync
  failure) is relied on; corruption *detection* is demonstrated in `docs/data_integrity.md`, fsync failure is not.
* **Restart recovery after WAL exhaustion** (see above).
* Separate API instances whose clocks differ still disagree about the TOTP window and the temp-token TTL by
  that difference; every other expiry is database-measured.
