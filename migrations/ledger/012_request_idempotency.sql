-- Forward migration: database-enforced request idempotency for single-ledger writes.
--
-- POST /v1/funding, /v1/cash-outs and /v1/accounts accepted an Idempotency-Key but never used it,
-- so a retried request credited, debited or created twice. A claim row is now inserted in the SAME
-- transaction as the write: the primary key makes a concurrent duplicate wait for the first request
-- and then see its stored result, and a rolled-back write leaves no claim behind.
--
-- Nothing in the journals changes; this only adds a table.

CREATE TABLE IF NOT EXISTS request_idempotency (
    scope VARCHAR(32) NOT NULL CHECK (scope IN ('FUNDING', 'CASH_OUT', 'CREATE_ACCOUNT')),
    idempotency_key VARCHAR(255) NOT NULL,
    request_hash VARCHAR(64) NOT NULL,
    result JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (scope, idempotency_key)
);

-- The claim is inserted with a placeholder and completed with the real result in the same
-- transaction, so the runtime role may update only that one column. It can never delete a claim.
GRANT SELECT, INSERT ON request_idempotency TO ledgerguard_app;
GRANT UPDATE (result) ON request_idempotency TO ledgerguard_app;
GRANT SELECT ON request_idempotency TO ledgerguard_reporter;
