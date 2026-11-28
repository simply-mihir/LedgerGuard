-- Forward migration: Immutable checksummed balance snapshots for as-of-time reconstruction

CREATE TABLE IF NOT EXISTS balance_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES ledger_accounts(account_id),
    ledger_id VARCHAR(64) NOT NULL,
    as_of_sequence BIGINT NOT NULL,
    as_of_timestamp TIMESTAMPTZ NOT NULL,
    posted_balance_minor BIGINT NOT NULL,
    held_amount_minor BIGINT NOT NULL CHECK (held_amount_minor >= 0),
    checksum VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (account_id, as_of_sequence)
);

CREATE INDEX IF NOT EXISTS idx_balance_snapshots_acct_ts
    ON balance_snapshots (account_id, as_of_timestamp DESC, as_of_sequence DESC);

DROP TRIGGER IF EXISTS trg_immutable_balance_snapshots ON balance_snapshots;
CREATE TRIGGER trg_immutable_balance_snapshots
    BEFORE UPDATE OR DELETE ON balance_snapshots
    FOR EACH ROW EXECUTE FUNCTION reject_journal_mutation();

GRANT SELECT, INSERT ON balance_snapshots TO ledgerguard_app;
GRANT SELECT ON balance_snapshots TO ledgerguard_reporter;
