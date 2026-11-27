-- Forward migration: database-enforced one-transfer-per-idempotency-key, plus missing indexes.
-- (Lookups by key go through the claims table's primary key, so no index on transfers is added.)
--
-- Background: transfers.idempotency_key had neither a unique constraint nor an index. The submit
-- path checked api_idempotency (written only after settlement) and then inserted, so concurrent
-- requests carrying the same key each created and settled their own transfer (a double spend,
-- reproduced with 6 concurrent submits debiting 6x). Existing rows may already contain such
-- duplicates, and posted history must never be rewritten, so a plain UNIQUE index (which would
-- fail on them) is not used. Instead each key is *claimed* once, by a trigger, from now on.

CREATE TABLE IF NOT EXISTS transfer_idempotency_claims (
    idempotency_key VARCHAR(255) PRIMARY KEY,
    transfer_id UUID NOT NULL UNIQUE REFERENCES transfers(transfer_id) ON DELETE CASCADE,
    claimed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- The earliest transfer owns each pre-existing key; later legacy duplicates are left untouched.
INSERT INTO transfer_idempotency_claims (idempotency_key, transfer_id, claimed_at)
SELECT DISTINCT ON (idempotency_key) idempotency_key, transfer_id, created_at
FROM transfers
ORDER BY idempotency_key, created_at, transfer_id
ON CONFLICT DO NOTHING;

DO $$
DECLARE
    dup_keys BIGINT;
BEGIN
    SELECT count(*) INTO dup_keys FROM (
        SELECT 1 FROM transfers GROUP BY idempotency_key HAVING count(*) > 1) d;
    IF dup_keys > 0 THEN
        RAISE NOTICE 'LEGACY DUPLICATES: % idempotency key(s) already map to more than one transfer. '
                     'They were left untouched (history is immutable) and need operator review.', dup_keys;
    END IF;
END
$$;

-- A second INSERT with the same key blocks until the first transaction ends, then fails with a
-- unique violation: concurrent duplicates are serialised by the database, not by application code.
CREATE OR REPLACE FUNCTION claim_transfer_idempotency_key()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
    INSERT INTO transfer_idempotency_claims (idempotency_key, transfer_id)
    VALUES (NEW.idempotency_key, NEW.transfer_id);
    RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_claim_transfer_idempotency_key ON transfers;
CREATE TRIGGER trg_claim_transfer_idempotency_key
    AFTER INSERT ON transfers
    FOR EACH ROW EXECUTE FUNCTION claim_transfer_idempotency_key();

DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'ledgerguard_app') THEN
        GRANT SELECT ON transfer_idempotency_claims TO ledgerguard_app;
    END IF;
    IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'ledgerguard_reporter') THEN
        GRANT SELECT ON transfer_idempotency_claims TO ledgerguard_reporter;
    END IF;
END
$$;

-- The worker's recovery sweep reads only unfinished transfers; keep it independent of how many
-- settled transfers have accumulated.
CREATE INDEX IF NOT EXISTS idx_transfers_open_created ON transfers (created_at)
    WHERE state IN ('ACCEPTED', 'PREPARING', 'COMMITTING', 'CANCELLING');

-- The operator transfer list is newest-first with a LIMIT.
CREATE INDEX IF NOT EXISTS idx_transfers_created_desc ON transfers (created_at DESC);
