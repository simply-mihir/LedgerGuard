-- Migration: 004_harden_auth_schema_and_permissions.sql
-- Description: Harden auth schema, store SHA-256 session token hashes, add TOTP replay protection, and enforce least-privilege role boundaries

-- 1. Explicitly revoke any and all access from the reporter role
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'ledgerguard_reporter') THEN
        REVOKE ALL ON operators FROM ledgerguard_reporter;
        REVOKE ALL ON operator_sessions FROM ledgerguard_reporter;
        REVOKE ALL ON operator_login_attempts FROM ledgerguard_reporter;
    END IF;
END
$$;

-- 2. Migrate operator_sessions to SHA-256 token hash and add idle expiry
DO $$
BEGIN
    IF EXISTS (
        SELECT FROM information_schema.columns
        WHERE table_name = 'operator_sessions' AND column_name = 'session_id'
    ) THEN
        -- Clear temporary dev sessions to cleanly adopt SHA-256 hash representation
        TRUNCATE TABLE operator_sessions;
        ALTER TABLE operator_sessions RENAME COLUMN session_id TO session_token_hash;
        ALTER TABLE operator_sessions ALTER COLUMN session_token_hash TYPE VARCHAR(64);
    END IF;
END
$$;

ALTER TABLE operator_sessions
    ADD COLUMN IF NOT EXISTS idle_expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '30 minutes');

CREATE INDEX IF NOT EXISTS idx_operator_sessions_idle
    ON operator_sessions(idle_expires_at);

-- 3. Enhance operators with TOTP replay prevention, staging expiry, and MFA failure tracking
ALTER TABLE operators
    ADD COLUMN IF NOT EXISTS pending_totp_secret VARCHAR(64) NULL,
    ADD COLUMN IF NOT EXISTS pending_totp_expires_at TIMESTAMPTZ NULL,
    ADD COLUMN IF NOT EXISTS last_totp_step BIGINT NULL,
    ADD COLUMN IF NOT EXISTS mfa_failed_attempts INT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS mfa_locked_until TIMESTAMPTZ NULL;

-- 4. Enhance login attempts with attempt type and compound source index
ALTER TABLE operator_login_attempts
    ADD COLUMN IF NOT EXISTS attempt_type VARCHAR(32) NOT NULL DEFAULT 'PASSWORD';

CREATE INDEX IF NOT EXISTS idx_login_attempts_source_window
    ON operator_login_attempts(identifier, ip_address, attempted_at);

-- 5. Enforce least-privilege for ledgerguard_app
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'ledgerguard_app') THEN
        REVOKE ALL ON operators, operator_sessions, operator_login_attempts FROM ledgerguard_app;
        GRANT SELECT, INSERT, UPDATE ON operators TO ledgerguard_app;
        GRANT SELECT, INSERT, UPDATE, DELETE ON operator_sessions TO ledgerguard_app;
        GRANT SELECT, INSERT ON operator_login_attempts TO ledgerguard_app;
    END IF;
END
$$;
