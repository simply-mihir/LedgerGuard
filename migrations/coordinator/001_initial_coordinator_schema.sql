-- Migration: 001_initial_coordinator_schema.sql
-- Description: Coordinator schema for customer registry, directory routing, transfer orchestration, and idempotency

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Customers table
CREATE TABLE IF NOT EXISTS customers (
    customer_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(128) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Account routing directory (mapping wallets to authoritative ledger instances)
CREATE TABLE IF NOT EXISTS account_directory (
    account_id UUID PRIMARY KEY,
    customer_id UUID NOT NULL REFERENCES customers(customer_id),
    ledger_id VARCHAR(64) NOT NULL,
    routing_version INT NOT NULL DEFAULT 1,
    provisioning_state VARCHAR(32) NOT NULL DEFAULT 'PROVISIONING'
        CHECK (provisioning_state IN ('PROVISIONING', 'READY', 'FAILED')),
    currency VARCHAR(3) NOT NULL DEFAULT 'INR',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- API request idempotency tracking
CREATE TABLE IF NOT EXISTS api_idempotency (
    idempotency_key VARCHAR(255) NOT NULL,
    operation_namespace VARCHAR(64) NOT NULL,
    payload_hash VARCHAR(64) NOT NULL,
    status_code INT NOT NULL,
    response_body JSONB NOT NULL,
    resource_id VARCHAR(128) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (idempotency_key, operation_namespace)
);

-- Coordinator transfer requests and state
CREATE TABLE IF NOT EXISTS transfers (
    transfer_id UUID PRIMARY KEY,
    idempotency_key VARCHAR(255) NOT NULL,
    source_account_id UUID NOT NULL,
    destination_account_id UUID NOT NULL,
    amount_minor BIGINT NOT NULL CHECK (amount_minor > 0),
    currency VARCHAR(3) NOT NULL DEFAULT 'INR',
    transfer_type VARCHAR(32) NOT NULL CHECK (transfer_type IN ('LOCAL', 'CROSS_LEDGER')),
    state VARCHAR(32) NOT NULL DEFAULT 'ACCEPTED'
        CHECK (state IN ('ACCEPTED', 'PREPARING', 'COMMITTING', 'CANCELLING', 'SETTLED', 'CANCELLED', 'REJECTED')),
    attention_required BOOLEAN NOT NULL DEFAULT FALSE,
    attention_reason TEXT NULL,
    source_ledger_id VARCHAR(64) NOT NULL,
    destination_ledger_id VARCHAR(64) NOT NULL,
    original_transfer_id UUID NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Durable transfer decisions (COMMIT / CANCEL) - immutable once decided
CREATE TABLE IF NOT EXISTS transfer_decisions (
    transfer_id UUID PRIMARY KEY REFERENCES transfers(transfer_id),
    decision VARCHAR(16) NOT NULL CHECK (decision IN ('COMMIT', 'CANCEL')),
    decision_version INT NOT NULL DEFAULT 1,
    reason TEXT NULL,
    decided_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Workflow events log
CREATE TABLE IF NOT EXISTS workflow_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transfer_id UUID NOT NULL REFERENCES transfers(transfer_id),
    event_type VARCHAR(64) NOT NULL,
    details JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Coordinator Outbox for reliable asynchronous messaging
CREATE TABLE IF NOT EXISTS outbox_events (
    outbox_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_id VARCHAR(128) NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL,
    attempts INT NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    delivered_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_outbox_pending 
    ON outbox_events (next_attempt_at) 
    WHERE delivered_at IS NULL;

-- Permissions for coordinator database
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'ledgerguard_app') THEN
        GRANT USAGE ON SCHEMA public TO ledgerguard_app;
        GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO ledgerguard_app;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO ledgerguard_app;
    END IF;

    IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'ledgerguard_reporter') THEN
        GRANT USAGE ON SCHEMA public TO ledgerguard_reporter;
        GRANT SELECT ON ALL TABLES IN SCHEMA public TO ledgerguard_reporter;
    END IF;
END
$$;
