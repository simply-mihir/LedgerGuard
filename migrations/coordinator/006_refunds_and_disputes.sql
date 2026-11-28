-- Forward migration: Refunds, chargebacks/disputes, and immutable dispute event trail

ALTER TABLE transfers
    ADD COLUMN IF NOT EXISTS refunded_amount_minor BIGINT NOT NULL DEFAULT 0 CHECK (refunded_amount_minor >= 0);

CREATE TABLE IF NOT EXISTS transfer_refunds (
    refund_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    original_transfer_id UUID NOT NULL REFERENCES transfers(transfer_id),
    refund_transfer_id UUID NOT NULL,
    idempotency_key VARCHAR(255) NOT NULL UNIQUE,
    payload_hash VARCHAR(64) NOT NULL,
    amount_minor BIGINT NOT NULL CHECK (amount_minor > 0),
    reason TEXT NOT NULL DEFAULT '',
    actor VARCHAR(128) NOT NULL DEFAULT 'operator',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_transfer_refunds_orig
    ON transfer_refunds (original_transfer_id, created_at ASC);

CREATE TABLE IF NOT EXISTS disputes (
    dispute_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transfer_id UUID NOT NULL REFERENCES transfers(transfer_id),
    state VARCHAR(32) NOT NULL CHECK (
        state IN (
            'OPENED', 'EVIDENCE_PENDING', 'UNDER_REVIEW', 'PROVISIONAL_HOLD',
            'APPROVED', 'REJECTED', 'COMPENSATION_PENDING', 'RESOLVED'
        )
    ),
    amount_minor BIGINT NOT NULL CHECK (amount_minor > 0),
    reason_code VARCHAR(64) NOT NULL,
    evidence_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    compensation_transfer_id UUID NULL,
    created_by VARCHAR(128) NOT NULL,
    decided_by VARCHAR(128) NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS dispute_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dispute_id UUID NOT NULL REFERENCES disputes(dispute_id),
    from_state VARCHAR(32) NULL,
    to_state VARCHAR(32) NOT NULL,
    actor VARCHAR(128) NOT NULL,
    reason_code VARCHAR(64) NULL,
    evidence_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dispute_events_dispute
    ON dispute_events (dispute_id, created_at ASC);

CREATE OR REPLACE FUNCTION reject_dispute_event_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Dispute events are immutable: % is prohibited', TG_OP
        USING ERRCODE = '55000';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_immutable_dispute_events ON dispute_events;
CREATE TRIGGER trg_immutable_dispute_events
    BEFORE UPDATE OR DELETE ON dispute_events
    FOR EACH ROW EXECUTE FUNCTION reject_dispute_event_mutation();

GRANT SELECT, INSERT ON transfer_refunds, dispute_events TO ledgerguard_app;
GRANT SELECT, INSERT, UPDATE ON disputes TO ledgerguard_app;
GRANT SELECT ON transfer_refunds, disputes, dispute_events TO ledgerguard_reporter;
