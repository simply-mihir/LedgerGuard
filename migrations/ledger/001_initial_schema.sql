-- Migration: 001_initial_schema.sql
-- Description: Core ledger schema with immutable double-entry journals, account balances, and constraint triggers

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Ledger accounts table
CREATE TABLE IF NOT EXISTS ledger_accounts (
    account_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NULL,
    account_type VARCHAR(16) NOT NULL CHECK (account_type IN ('LIABILITY', 'ASSET', 'CONTROL')),
    normal_side VARCHAR(6) NOT NULL CHECK (normal_side IN ('DEBIT', 'CREDIT')),
    currency VARCHAR(3) NOT NULL DEFAULT 'INR',
    status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'FROZEN', 'CLOSED')),
    name VARCHAR(128) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Authoritative account balances and lock target
CREATE TABLE IF NOT EXISTS account_balances (
    account_id UUID PRIMARY KEY REFERENCES ledger_accounts(account_id) ON DELETE RESTRICT,
    posted_balance_minor BIGINT NOT NULL DEFAULT 0,
    held_amount_minor BIGINT NOT NULL DEFAULT 0 CHECK (held_amount_minor >= 0),
    account_sequence BIGINT NOT NULL DEFAULT 0,
    version BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Journal headers (immutable)
CREATE TABLE IF NOT EXISTS journal_headers (
    journal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transfer_id UUID NULL,
    operation_type VARCHAR(64) NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'INR',
    correlation_id VARCHAR(128) NULL,
    description TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Journal lines (immutable)
CREATE TABLE IF NOT EXISTS journal_lines (
    line_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    journal_id UUID NOT NULL REFERENCES journal_headers(journal_id) ON DELETE RESTRICT,
    line_no INT NOT NULL,
    account_id UUID NOT NULL REFERENCES ledger_accounts(account_id) ON DELETE RESTRICT,
    side VARCHAR(6) NOT NULL CHECK (side IN ('DEBIT', 'CREDIT')),
    amount_minor BIGINT NOT NULL CHECK (amount_minor > 0),
    account_sequence BIGINT NOT NULL,
    CONSTRAINT uq_journal_line UNIQUE (journal_id, line_no),
    CONSTRAINT uq_account_sequence UNIQUE (account_id, account_sequence)
);

CREATE INDEX IF NOT EXISTS idx_journal_lines_account_seq 
    ON journal_lines (account_id, account_sequence);
CREATE INDEX IF NOT EXISTS idx_journal_lines_journal_id 
    ON journal_lines (journal_id);
CREATE INDEX IF NOT EXISTS idx_journal_headers_transfer_id 
    ON journal_headers (transfer_id);

-- Audit log
CREATE TABLE IF NOT EXISTS audit_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor VARCHAR(64) NOT NULL DEFAULT 'system',
    action VARCHAR(64) NOT NULL,
    resource_id VARCHAR(128) NOT NULL,
    old_state JSONB NULL,
    new_state JSONB NULL,
    correlation_id VARCHAR(128) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Immutability enforcement trigger function
CREATE OR REPLACE FUNCTION reject_journal_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Financial journal records are immutable: % on % is prohibited', TG_OP, TG_TABLE_NAME
        USING ERRCODE = '55000';
END;
$$ LANGUAGE plpgsql;

-- Immutability triggers on journal headers and lines
DROP TRIGGER IF EXISTS trg_immutable_journal_headers_mutation ON journal_headers;
CREATE TRIGGER trg_immutable_journal_headers_mutation
    BEFORE UPDATE OR DELETE ON journal_headers
    FOR EACH ROW EXECUTE FUNCTION reject_journal_mutation();

DROP TRIGGER IF EXISTS trg_immutable_journal_headers_truncate ON journal_headers;
CREATE TRIGGER trg_immutable_journal_headers_truncate
    BEFORE TRUNCATE ON journal_headers
    FOR EACH STATEMENT EXECUTE FUNCTION reject_journal_mutation();

DROP TRIGGER IF EXISTS trg_immutable_journal_lines_mutation ON journal_lines;
CREATE TRIGGER trg_immutable_journal_lines_mutation
    BEFORE UPDATE OR DELETE ON journal_lines
    FOR EACH ROW EXECUTE FUNCTION reject_journal_mutation();

DROP TRIGGER IF EXISTS trg_immutable_journal_lines_truncate ON journal_lines;
CREATE TRIGGER trg_immutable_journal_lines_truncate
    BEFORE TRUNCATE ON journal_lines
    FOR EACH STATEMENT EXECUTE FUNCTION reject_journal_mutation();

-- Deferred constraint trigger function to enforce balanced journals
CREATE OR REPLACE FUNCTION verify_journal_balanced()
RETURNS TRIGGER AS $$
DECLARE
    v_line_count INT;
    v_net_balance BIGINT;
BEGIN
    SELECT COUNT(*), COALESCE(SUM(CASE WHEN side = 'DEBIT' THEN amount_minor ELSE -amount_minor END), 0)
    INTO v_line_count, v_net_balance
    FROM journal_lines
    WHERE journal_id = NEW.journal_id;

    IF v_line_count < 2 THEN
        RAISE EXCEPTION 'Journal % must contain at least 2 lines; found %', NEW.journal_id, v_line_count
            USING ERRCODE = '23514';
    END IF;

    IF v_net_balance <> 0 THEN
        RAISE EXCEPTION 'Journal % is unbalanced: debits minus credits is % (expected 0)', NEW.journal_id, v_net_balance
            USING ERRCODE = '23514';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_verify_journal_balanced ON journal_headers;
CREATE CONSTRAINT TRIGGER trg_verify_journal_balanced
    AFTER INSERT ON journal_headers
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION verify_journal_balanced();

-- Seed system accounts
INSERT INTO ledger_accounts (account_id, account_type, normal_side, currency, status, name)
VALUES 
    ('00000000-0000-0000-0000-000000000001', 'ASSET', 'DEBIT', 'INR', 'ACTIVE', 'Platform Cash Asset'),
    ('00000000-0000-0000-0000-000000000002', 'CONTROL', 'DEBIT', 'INR', 'ACTIVE', 'Inter-Ledger Clearing Control')
ON CONFLICT (account_id) DO NOTHING;

INSERT INTO account_balances (account_id, posted_balance_minor, held_amount_minor, account_sequence, version)
VALUES 
    ('00000000-0000-0000-0000-000000000001', 0, 0, 0, 0),
    ('00000000-0000-0000-0000-000000000002', 0, 0, 0, 0)
ON CONFLICT (account_id) DO NOTHING;
