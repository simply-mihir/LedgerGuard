-- Forward migration: Durable per-participant circuit breaker and backpressure state

CREATE TABLE IF NOT EXISTS participant_resilience_state (
    participant_id VARCHAR(64) PRIMARY KEY,
    circuit_state VARCHAR(16) NOT NULL DEFAULT 'CLOSED' CHECK (circuit_state IN ('CLOSED', 'OPEN', 'HALF_OPEN')),
    failure_count INT NOT NULL DEFAULT 0,
    success_count INT NOT NULL DEFAULT 0,
    in_flight_count INT NOT NULL DEFAULT 0,
    half_open_probes INT NOT NULL DEFAULT 0,
    last_failure_at TIMESTAMPTZ NULL,
    next_probe_at TIMESTAMPTZ NULL,
    p95_latency_ms DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    outbox_depth INT NOT NULL DEFAULT 0,
    oldest_pending_age_seconds DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    reason TEXT NOT NULL DEFAULT 'Healthy',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO participant_resilience_state (participant_id, circuit_state, reason)
VALUES
    ('ledger-1', 'CLOSED', 'Nominal'),
    ('ledger-2', 'CLOSED', 'Nominal')
ON CONFLICT (participant_id) DO NOTHING;

CREATE TABLE IF NOT EXISTS resilience_audit_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    participant_id VARCHAR(64) NOT NULL,
    from_state VARCHAR(16) NULL,
    to_state VARCHAR(16) NOT NULL,
    reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

GRANT SELECT, INSERT, UPDATE ON participant_resilience_state TO ledgerguard_app;
GRANT SELECT, INSERT ON resilience_audit_events TO ledgerguard_app;
GRANT SELECT ON participant_resilience_state, resilience_audit_events TO ledgerguard_reporter;
