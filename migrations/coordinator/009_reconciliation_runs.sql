-- Forward migration: durable reconciliation run store (replaces a process-local dict)

CREATE TABLE IF NOT EXISTS reconciliation_runs (
    run_id UUID PRIMARY KEY,
    run_at TIMESTAMPTZ NOT NULL,
    status VARCHAR(16) NOT NULL,
    report JSONB NOT NULL,
    requested_by VARCHAR(255) NOT NULL DEFAULT 'unknown',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reconciliation_runs_created
    ON reconciliation_runs(created_at DESC);

GRANT SELECT, INSERT ON reconciliation_runs TO ledgerguard_app;
GRANT SELECT ON reconciliation_runs TO ledgerguard_reporter;
