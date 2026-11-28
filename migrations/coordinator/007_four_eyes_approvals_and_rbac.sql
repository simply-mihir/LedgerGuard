-- Forward migration: Four-eyes dual-control approvals and expanded RBAC roles

DO $$
DECLARE
    c_name TEXT;
BEGIN
    SELECT conname INTO c_name
    FROM pg_constraint
    WHERE conrelid = 'operators'::regclass
      AND contype = 'c'
      AND pg_get_constraintdef(oid) LIKE '%role%';
    IF c_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE operators DROP CONSTRAINT %I', c_name);
    END IF;
END $$;

ALTER TABLE operators
    ADD CONSTRAINT operators_role_check
    CHECK (role IN ('VIEWER', 'OPERATOR', 'APPROVER', 'AUDITOR', 'ADMIN'));

CREATE TABLE IF NOT EXISTS approval_requests (
    request_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action_type VARCHAR(64) NOT NULL,
    state VARCHAR(32) NOT NULL CHECK (
        state IN ('DRAFT', 'PENDING_APPROVAL', 'APPROVED', 'REJECTED', 'EXPIRED', 'EXECUTED', 'FAILED')
    ),
    payload JSONB NOT NULL,
    payload_hash VARCHAR(64) NOT NULL,
    initiator_id VARCHAR(128) NOT NULL,
    initiator_role VARCHAR(32) NOT NULL,
    approver_id VARCHAR(128) NULL,
    approver_role VARCHAR(32) NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    executed_at TIMESTAMPTZ NULL,
    execution_result JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS approval_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID NOT NULL REFERENCES approval_requests(request_id),
    from_state VARCHAR(32) NULL,
    to_state VARCHAR(32) NOT NULL,
    actor_id VARCHAR(128) NOT NULL,
    actor_role VARCHAR(32) NOT NULL,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_approval_requests_state
    ON approval_requests (state, expires_at);

CREATE OR REPLACE FUNCTION reject_approval_event_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Approval audit events are immutable: % is prohibited', TG_OP
        USING ERRCODE = '55000';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_immutable_approval_events ON approval_events;
CREATE TRIGGER trg_immutable_approval_events
    BEFORE UPDATE OR DELETE ON approval_events
    FOR EACH ROW EXECUTE FUNCTION reject_approval_event_mutation();

GRANT SELECT, INSERT, UPDATE ON approval_requests TO ledgerguard_app;
GRANT SELECT, INSERT ON approval_events TO ledgerguard_app;
GRANT SELECT ON approval_requests, approval_events TO ledgerguard_reporter;
