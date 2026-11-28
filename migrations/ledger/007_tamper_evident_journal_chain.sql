-- Forward migration: Add tamper-evident SHA-256 hash chains and Merkle checkpoints to journal_headers

CREATE EXTENSION IF NOT EXISTS pgcrypto;

ALTER TABLE journal_headers
    ADD COLUMN IF NOT EXISTS ledger_id VARCHAR(64) NOT NULL DEFAULT 'ledger',
    ADD COLUMN IF NOT EXISTS sequence_number BIGINT UNIQUE,
    ADD COLUMN IF NOT EXISTS previous_hash VARCHAR(64),
    ADD COLUMN IF NOT EXISTS entry_hash VARCHAR(64),
    ADD COLUMN IF NOT EXISTS hash_schema_version INT NOT NULL DEFAULT 1;

CREATE TABLE IF NOT EXISTS journal_chain_head (
    id INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    last_sequence BIGINT NOT NULL DEFAULT 0,
    last_hash VARCHAR(64) NOT NULL
);

INSERT INTO journal_chain_head (id, last_sequence, last_hash)
VALUES (1, 0, repeat('0', 64))
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS journal_checkpoints (
    checkpoint_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ledger_id VARCHAR(64) NOT NULL,
    first_sequence BIGINT NOT NULL,
    last_sequence BIGINT NOT NULL,
    merkle_root VARCHAR(64) NOT NULL,
    leaf_count INT NOT NULL,
    schema_version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (first_sequence >= 1),
    CHECK (last_sequence >= first_sequence),
    CHECK (leaf_count >= 1)
);

CREATE INDEX IF NOT EXISTS idx_journal_checkpoints_ledger_seq
    ON journal_checkpoints (ledger_id, last_sequence DESC);

-- Canonical hash computation function
CREATE OR REPLACE FUNCTION compute_journal_entry_hash(
    p_schema_version INT,
    p_ledger_id VARCHAR,
    p_sequence_number BIGINT,
    p_previous_hash VARCHAR,
    p_journal_id UUID,
    p_created_at TIMESTAMPTZ,
    p_operation_type VARCHAR,
    p_currency VARCHAR,
    p_transfer_id UUID,
    p_lines_canonical TEXT
) RETURNS VARCHAR AS $$
DECLARE
    v_ts TEXT;
    v_payload TEXT;
BEGIN
    v_ts := to_char(p_created_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"');
    v_payload := 'LEDGERGUARD_JOURNAL_V1'
        || '|' || p_schema_version::TEXT
        || '|' || p_ledger_id
        || '|' || p_sequence_number::TEXT
        || '|' || p_previous_hash
        || '|' || p_journal_id::TEXT
        || '|' || v_ts
        || '|' || p_operation_type
        || '|' || p_currency
        || '|' || COALESCE(p_transfer_id::TEXT, '')
        || '|' || COALESCE(p_lines_canonical, '');
    RETURN encode(digest(convert_to(v_payload, 'UTF8'), 'sha256'), 'hex');
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Update immutability trigger so ONLY the initial one-time seal (OLD.entry_hash IS NULL -> NEW.entry_hash IS NOT NULL)
-- is permitted from the SECURITY DEFINER sealing trigger; all other mutations remain strictly rejected.
CREATE OR REPLACE FUNCTION reject_journal_mutation()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND TG_TABLE_NAME = 'journal_headers'
       AND OLD.entry_hash IS NULL AND NEW.entry_hash IS NOT NULL
       AND OLD.journal_id = NEW.journal_id
       AND OLD.operation_type = NEW.operation_type
       AND OLD.currency = NEW.currency
       AND OLD.created_at = NEW.created_at
       AND COALESCE(OLD.transfer_id::TEXT, '') = COALESCE(NEW.transfer_id::TEXT, '') THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'Financial journal records are immutable: % on % is prohibited', TG_OP, TG_TABLE_NAME
        USING ERRCODE = '55000';
END;
$$ LANGUAGE plpgsql;

-- Helper to resolve canonical ledger_id from database name
CREATE OR REPLACE FUNCTION resolve_canonical_ledger_id()
RETURNS VARCHAR AS $$
DECLARE
    v_db TEXT := current_database();
BEGIN
    IF v_db LIKE 'ledger1%' THEN
        RETURN 'ledger-1';
    ELSIF v_db LIKE 'ledger2%' THEN
        RETURN 'ledger-2';
    ELSE
        RETURN v_db;
    END IF;
END;
$$ LANGUAGE plpgsql STABLE;

-- Deferred constraint trigger that seals each posted journal transactionally
CREATE OR REPLACE FUNCTION seal_journal_entry()
RETURNS TRIGGER
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_head_seq BIGINT;
    v_head_hash VARCHAR(64);
    v_new_seq BIGINT;
    v_ledger_id VARCHAR(64);
    v_lines_canonical TEXT;
    v_entry_hash VARCHAR(64);
BEGIN
    IF NEW.entry_hash IS NOT NULL THEN
        RETURN NEW;
    END IF;

    SELECT last_sequence, last_hash
    INTO v_head_seq, v_head_hash
    FROM journal_chain_head
    WHERE id = 1
    FOR UPDATE;

    v_new_seq := v_head_seq + 1;
    v_ledger_id := resolve_canonical_ledger_id();

    SELECT COALESCE(
        string_agg(
            line_no::TEXT || ':' || account_id::TEXT || ':' || side || ':' || amount_minor::TEXT,
            ';' ORDER BY line_no ASC
        ),
        ''
    )
    INTO v_lines_canonical
    FROM journal_lines
    WHERE journal_id = NEW.journal_id;

    v_entry_hash := compute_journal_entry_hash(
        1,
        v_ledger_id,
        v_new_seq,
        v_head_hash,
        NEW.journal_id,
        NEW.created_at,
        NEW.operation_type,
        NEW.currency,
        NEW.transfer_id,
        v_lines_canonical
    );

    UPDATE journal_headers
    SET ledger_id = v_ledger_id,
        sequence_number = v_new_seq,
        previous_hash = v_head_hash,
        entry_hash = v_entry_hash,
        hash_schema_version = 1
    WHERE journal_id = NEW.journal_id;

    UPDATE journal_chain_head
    SET last_sequence = v_new_seq,
        last_hash = v_entry_hash
    WHERE id = 1;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_seal_journal_entry ON journal_headers;
CREATE CONSTRAINT TRIGGER trg_seal_journal_entry
    AFTER INSERT ON journal_headers
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION seal_journal_entry();

-- Backfill any pre-existing unsealed journal entries in deterministic chronological order
DO $$
DECLARE
    r RECORD;
    v_head_seq BIGINT;
    v_head_hash VARCHAR(64);
    v_ledger_id VARCHAR(64);
    v_lines TEXT;
    v_hash VARCHAR(64);
BEGIN
    v_ledger_id := resolve_canonical_ledger_id();
    SELECT last_sequence, last_hash INTO v_head_seq, v_head_hash FROM journal_chain_head WHERE id = 1 FOR UPDATE;

    FOR r IN
        SELECT journal_id, created_at, operation_type, currency, transfer_id
        FROM journal_headers
        WHERE entry_hash IS NULL
        ORDER BY created_at ASC, journal_id ASC
    LOOP
        v_head_seq := v_head_seq + 1;
        SELECT COALESCE(
            string_agg(
                line_no::TEXT || ':' || account_id::TEXT || ':' || side || ':' || amount_minor::TEXT,
                ';' ORDER BY line_no ASC
            ),
            ''
        )
        INTO v_lines
        FROM journal_lines
        WHERE journal_id = r.journal_id;

        v_hash := compute_journal_entry_hash(
            1, v_ledger_id, v_head_seq, v_head_hash,
            r.journal_id, r.created_at, r.operation_type, r.currency, r.transfer_id, v_lines
        );

        UPDATE journal_headers
        SET ledger_id = v_ledger_id,
            sequence_number = v_head_seq,
            previous_hash = v_head_hash,
            entry_hash = v_hash,
            hash_schema_version = 1
        WHERE journal_id = r.journal_id;

        v_head_hash := v_hash;
    END LOOP;

    UPDATE journal_chain_head
    SET last_sequence = v_head_seq,
        last_hash = v_head_hash
    WHERE id = 1;
END $$;

-- Least-privilege grants
GRANT SELECT ON journal_chain_head TO ledgerguard_app, ledgerguard_reporter;
GRANT SELECT, INSERT ON journal_checkpoints TO ledgerguard_app;
GRANT SELECT ON journal_checkpoints TO ledgerguard_reporter;
