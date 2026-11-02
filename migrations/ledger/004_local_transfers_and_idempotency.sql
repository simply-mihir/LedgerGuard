-- Migration: 004_local_transfers_and_idempotency.sql
-- Description: Tables for local transfer persistence, unique reversal links, and request idempotency

CREATE TABLE IF NOT EXISTS local_transfers (
    transfer_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key VARCHAR(255) NOT NULL UNIQUE,
    payload_hash VARCHAR(64) NOT NULL,
    source_account_id UUID NOT NULL REFERENCES ledger_accounts(account_id),
    destination_account_id UUID NOT NULL REFERENCES ledger_accounts(account_id),
    amount_minor BIGINT NOT NULL CHECK (amount_minor > 0),
    currency VARCHAR(3) NOT NULL DEFAULT 'INR',
    journal_id UUID NOT NULL REFERENCES journal_headers(journal_id),
    status VARCHAR(32) NOT NULL DEFAULT 'SETTLED' CHECK (status IN ('SETTLED', 'REVERSED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS transfer_reversals (
    reversal_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_transfer_id UUID NOT NULL UNIQUE REFERENCES local_transfers(transfer_id),
    reversal_transfer_id UUID NOT NULL UNIQUE REFERENCES local_transfers(transfer_id),
    amount_minor BIGINT NOT NULL,
    reason TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS idempotency_records (
    idempotency_key VARCHAR(255) NOT NULL,
    operation_namespace VARCHAR(64) NOT NULL,
    payload_hash VARCHAR(64) NOT NULL,
    status_code INT NOT NULL,
    response_body JSONB NOT NULL,
    resource_id VARCHAR(128) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (idempotency_key, operation_namespace)
);

CREATE INDEX IF NOT EXISTS idx_local_transfers_source 
    ON local_transfers(source_account_id);
CREATE INDEX IF NOT EXISTS idx_local_transfers_dest 
    ON local_transfers(destination_account_id);

DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'ledgerguard_app') THEN
        GRANT SELECT, INSERT, UPDATE ON local_transfers TO ledgerguard_app;
        GRANT SELECT, INSERT ON transfer_reversals TO ledgerguard_app;
        GRANT SELECT, INSERT, UPDATE ON idempotency_records TO ledgerguard_app;
    END IF;

    IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'ledgerguard_reporter') THEN
        GRANT SELECT ON local_transfers TO ledgerguard_reporter;
        GRANT SELECT ON transfer_reversals TO ledgerguard_reporter;
        GRANT SELECT ON idempotency_records TO ledgerguard_reporter;
    END IF;
END
$$;
