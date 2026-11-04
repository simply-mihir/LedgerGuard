-- Migration: 003_operator_auth_schema.sql
-- Description: Operator authentication, Argon2id credentials, TOTP multi-factor secrets, and server-managed sessions

CREATE TABLE IF NOT EXISTS operators (
    operator_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(64) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    totp_secret VARCHAR(64) NULL,
    totp_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    role VARCHAR(32) NOT NULL DEFAULT 'OPERATOR' CHECK (role IN ('OPERATOR', 'ADMIN', 'AUDITOR')),
    failed_attempts INT NOT NULL DEFAULT 0,
    locked_until TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS operator_sessions (
    session_id VARCHAR(128) PRIMARY KEY,
    operator_id UUID NOT NULL REFERENCES operators(operator_id) ON DELETE CASCADE,
    csrf_token VARCHAR(64) NOT NULL,
    ip_address VARCHAR(45) NULL,
    user_agent TEXT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_operator_sessions_expires
    ON operator_sessions(expires_at);

CREATE TABLE IF NOT EXISTS operator_login_attempts (
    attempt_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    identifier VARCHAR(255) NOT NULL,
    ip_address VARCHAR(45) NULL,
    success BOOLEAN NOT NULL,
    attempted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_login_attempts_window
    ON operator_login_attempts(identifier, attempted_at);

-- Grant permissions to application role
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'ledgerguard_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON operators TO ledgerguard_app;
        GRANT SELECT, INSERT, UPDATE, DELETE ON operator_sessions TO ledgerguard_app;
        GRANT SELECT, INSERT, UPDATE, DELETE ON operator_login_attempts TO ledgerguard_app;
    END IF;

    IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'ledgerguard_reporter') THEN
        GRANT SELECT ON operators TO ledgerguard_reporter;
        GRANT SELECT ON operator_sessions TO ledgerguard_reporter;
        GRANT SELECT ON operator_login_attempts TO ledgerguard_reporter;
    END IF;
END
$$;
