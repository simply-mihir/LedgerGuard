-- Forward migration: Coordinator-side trust-boundary attestation for ledger Merkle checkpoints

CREATE TABLE IF NOT EXISTS journal_checkpoint_attestations (
    attestation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ledger_id VARCHAR(64) NOT NULL,
    checkpoint_id UUID NOT NULL,
    first_sequence BIGINT NOT NULL,
    last_sequence BIGINT NOT NULL,
    merkle_root VARCHAR(64) NOT NULL,
    leaf_count INT NOT NULL,
    schema_version INT NOT NULL DEFAULT 1,
    attested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (ledger_id, checkpoint_id)
);

GRANT SELECT, INSERT ON journal_checkpoint_attestations TO ledgerguard_app;
GRANT SELECT ON journal_checkpoint_attestations TO ledgerguard_reporter;
