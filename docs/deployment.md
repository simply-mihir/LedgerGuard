# Deployment hardening guide

This page says what the code enforces, what you must provide around it, and what has **not**
been verified. LedgerGuard is a verified reference implementation, not a managed service; the
items under "Not verified" need your own review before real money is involved.

## What the code enforces (`LEDGERGUARD_ENV=production`)

Settings validation fails at startup, so an unsafe production configuration never serves traffic:

| Check | Why |
|---|---|
| `INTERNAL_SERVICE_SECRET` is not the demo value | worker-to-API trust |
| `LEDGERGUARD_COOKIE_SECURE` is not `false` | session cookies carry the `Secure` flag |
| `FAULT_INJECTION_ENABLED` is not on | no chaos or fault endpoints |
| `LEDGERGUARD_TRUSTED_ORIGINS` is set and every origin is `https://` | CSRF/origin allow-list and CORS |
| No database URL contains a demo password | default credentials never reach production |
| `API_SERVICE_TOKENS` entries are valid (>= 32 chars, unique, named, one role per name) | per-caller credentials |

The shared demo bearer token is rejected in production; use named service credentials
(`API_SERVICE_TOKENS=name:ROLE:token,...`). Workers and automation get the least role they need
(a service credential can never approve a dual-control request).

## Rate limiting

Every route except `/health` goes through an in-process token bucket per client
(`API_RATE_LIMIT_PER_MINUTE`, default 1200 reads; `API_WRITE_RATE_LIMIT_PER_MINUTE`, default 600
writes; `0` disables). Exceeding it returns `429` with `Retry-After`. Login additionally has its
own progressive throttling and lockout.

Limits of this design: the buckets are per process (N workers allow N times the rate), memory is
bounded (10,000 clients, least-recently-used eviction), and the client is the network peer, or the
right-most `X-Forwarded-For` entry only when the peer is in `LEDGERGUARD_TRUSTED_PROXIES`. Keep that
list to your own reverse proxy. For a hard limit, also configure rate limits at the proxy.

## TLS

The application speaks plain HTTP and expects a TLS-terminating reverse proxy in front of it.

* Terminate TLS 1.2+ at the proxy, redirect HTTP to HTTPS, send `Strict-Transport-Security`.
* Forward `X-Forwarded-For` and `X-Forwarded-Proto`; list only the proxy in
  `LEDGERGUARD_TRUSTED_PROXIES`.
* Expose only the console and API ports to the proxy; never the databases.
* Database links: add `sslmode=verify-full` (and the CA) to the three database URLs if the
  databases are not on a private loopback or private network. **This repository's tests and
  campaigns run databases without TLS on localhost; TLS to PostgreSQL is not exercised here.**

## Secrets

* Provide secrets through the environment or a secrets manager, never through git or images.
  `.env.example` contains only demo values.
* Rotate a service token with zero downtime: add the new token under the same name, deploy
  callers, remove the old token. Revoke by removing the entry and restarting.
* Use distinct database roles: the application role has no DDL rights; the admin role is used
  only by migrations.

## Backup and restore

* Take logical backups of all three databases together, and enable WAL archiving for
  point-in-time recovery of each. The three databases must be restored to a **consistent
  moment**; restore, then run forward recovery and the stopped-and-drained reconciliation.
* `docs/disaster_recovery.md` and `scripts/demo_disaster_recovery.sh --confirm-disposable`
  exercise backup, restore, journal-chain verification and reconciliation on disposable
  databases, and measure RPO relative to the captured backup point.
* Schedule that drill against your real backup artefacts, and alert on failure.
* Journal hash chains and Merkle checkpoints make silent tampering of restored history
  detectable; keep the latest checkpoint attestation outside the database.

## Operations checklist

1. `uv run python -m ledgerguard.cli migrate --target all` (forward migrations only).
2. Create the first administrator through the CLI, enable MFA, store recovery codes offline.
3. Run workers (`recover_pending_transfers`) under a supervisor that restarts them; recovery is
   idempotent.
4. Scrape traces/metrics; alert on non-terminal transfers older than your SLA, reconciliation
   failures, and 429 spikes.
5. Run `verify-all-ledgers` and the cross-ledger reconciliation on a schedule.

## Not verified

* No third-party penetration test or security audit has been done.
* No high-availability setup: single instance of each database and service.
* Database TLS, proxy configuration, WAL archiving and off-site backups are described, not
  tested, in this repository.
* Per-process rate limits do not replace a WAF or edge protection.
