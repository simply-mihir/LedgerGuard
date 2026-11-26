# LedgerGuard V2 Threat Model

## 1. Authentication & Session Security
- Passwords hashed with Argon2id; TOTP secrets protected with RFC 6238 replay prevention (`last_totp_step`).
- Session tokens stored as SHA-256 digests (`session_token_hash`); cookies use `HttpOnly`, `SameSite=Lax`, and `Secure` outside local dev.
- CSRF tokens and trusted-origin checks protect all state-changing routes.
- `ledgerguard_reporter` is strictly denied access to `operators`, `operator_sessions`, and `operator_login_attempts` (Invariant `I16`).

## 2. Tamper-Evident Journals & Snapshots
- `journal_headers` and `journal_lines` reject `UPDATE`/`DELETE`/`TRUNCATE` via triggers.
- Canonical SHA-256 hash chains and cross-boundary Merkle checkpoints in `coordinator_db` detect privileged/offline DB edits.
- `balance_snapshots` are immutable and SHA-256 checksummed; corrupted snapshots trigger `SNAPSHOT_CORRUPTED` and fall back to full replay.

## 3. Dual Control & Lab Isolation
- Sensitive actions require four-eyes approval (`initiator_id != approver_id`), MFA verification, recent auth, and immutable payload hash verification.
- Chaos, tamper, and disaster-recovery endpoints/drills are disabled in `LEDGERGUARD_ENV=production` and require explicit disposable guards.

## 4. Telemetry Redaction
- OpenTelemetry span attributes strip `password`, `secret`, `token`, `totp`, `csrf`, `cookie`, `authorization`, `session`, `email`, and `phone`, and bucket monetary amounts.
