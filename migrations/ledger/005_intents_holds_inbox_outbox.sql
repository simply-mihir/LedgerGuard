-- Migration: 005_intents_holds_inbox_outbox.sql
-- Description: Participant transfer intents, durable holds, command inbox, and outbox

CREATE TABLE IF NOT EXISTS transfer_intents (
    intent_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transfer_id UUID NOT NULL UNIQUE,
    direction VARCHAR(16) NOT NULL CHECK (direction IN ('OUTGOING', 'INCOMING')),
    source_account_id UUID NOT NULL,
    destination_account_id UUID NOT NULL,
    amount_minor BIGINT NOT NULL CHECK (amount_minor > 0),
    currency VARCHAR(3) NOT NULL DEFAULT 'INR',
    status VARCHAR(16) NOT NULL CHECK (status IN ('PREPARED', 'CONFIRMED', 'CANCELLED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE transfer_intents DROP CONSTRAINT IF EXISTS transfer_intents_source_account_id_fkey;

CREATE TABLE IF NOT EXISTS holds (
    hold_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES ledger_accounts(account_id),
    transfer_id UUID NOT NULL UNIQUE,
    amount_minor BIGINT NOT NULL CHECK (amount_minor > 0),
    status VARCHAR(16) NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'RELEASED', 'CONSUMED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS command_inbox (
    command_id VARCHAR(255) PRIMARY KEY,
    transfer_id UUID NOT NULL,
    command_type VARCHAR(64) NOT NULL,
    payload_hash VARCHAR(64) NOT NULL,
    result JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS participant_outbox (
    outbox_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_id VARCHAR(128) NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL,
    attempts INT NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    delivered_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_holds_account_active 
    ON holds(account_id) WHERE status = 'ACTIVE';
CREATE INDEX IF NOT EXISTS idx_transfer_intents_transfer 
    ON transfer_intents(transfer_id);
CREATE INDEX IF NOT EXISTS idx_command_inbox_transfer 
    ON command_inbox(transfer_id);

-- Stored procedure for source prepare (funds reservation)
CREATE OR REPLACE FUNCTION source_prepare(
    p_command_id VARCHAR(255),
    p_transfer_id UUID,
    p_source_account_id UUID,
    p_dest_account_id UUID,
    p_amount_minor BIGINT,
    p_currency VARCHAR(3),
    p_payload_hash VARCHAR(64)
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_existing_inbox RECORD;
    v_intent RECORD;
    v_cur_posted BIGINT;
    v_cur_held BIGINT;
    v_status VARCHAR;
    v_res JSONB;
BEGIN
    -- 1. Check inbox deduplication
    SELECT result, payload_hash INTO v_existing_inbox
    FROM command_inbox WHERE command_id = p_command_id;
    IF FOUND THEN
        IF v_existing_inbox.payload_hash <> p_payload_hash THEN
            RAISE EXCEPTION 'Idempotency conflict on command %', p_command_id USING ERRCODE = '23505';
        END IF;
        RETURN v_existing_inbox.result;
    END IF;

    -- 2. Check if a cancellation tombstone already exists for this transfer
    SELECT status INTO v_intent FROM transfer_intents WHERE transfer_id = p_transfer_id;
    IF FOUND AND v_intent.status = 'CANCELLED' THEN
        v_res := jsonb_build_object(
            'status', 'REJECTED',
            'reason', 'Transfer previously cancelled by tombstone',
            'transfer_id', p_transfer_id
        );
        INSERT INTO command_inbox (command_id, transfer_id, command_type, payload_hash, result)
        VALUES (p_command_id, p_transfer_id, 'SOURCE_PREPARE', p_payload_hash, v_res);
        RETURN v_res;
    END IF;

    -- 3. Lock account and verify status and available balance
    SELECT b.posted_balance_minor, b.held_amount_minor, a.status
    INTO v_cur_posted, v_cur_held, v_status
    FROM account_balances b
    JOIN ledger_accounts a ON b.account_id = a.account_id
    WHERE b.account_id = p_source_account_id
    FOR UPDATE OF b;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Account % not found', p_source_account_id USING ERRCODE = '23503';
    END IF;

    IF v_status <> 'ACTIVE' THEN
        v_res := jsonb_build_object(
            'status', 'REJECTED',
            'reason', 'Account is not ACTIVE (' || v_status || ')',
            'transfer_id', p_transfer_id
        );
        INSERT INTO command_inbox (command_id, transfer_id, command_type, payload_hash, result)
        VALUES (p_command_id, p_transfer_id, 'SOURCE_PREPARE', p_payload_hash, v_res);
        RETURN v_res;
    END IF;

    IF (v_cur_posted - v_cur_held) < p_amount_minor THEN
        v_res := jsonb_build_object(
            'status', 'REJECTED',
            'reason', 'Insufficient available funds: available ' || (v_cur_posted - v_cur_held) || ', required ' || p_amount_minor,
            'transfer_id', p_transfer_id
        );
        INSERT INTO command_inbox (command_id, transfer_id, command_type, payload_hash, result)
        VALUES (p_command_id, p_transfer_id, 'SOURCE_PREPARE', p_payload_hash, v_res);
        RETURN v_res;
    END IF;

    -- 4. Create active hold and update held_amount_minor
    INSERT INTO holds (hold_id, account_id, transfer_id, amount_minor, status)
    VALUES (gen_random_uuid(), p_source_account_id, p_transfer_id, p_amount_minor, 'ACTIVE');

    UPDATE account_balances
    SET held_amount_minor = held_amount_minor + p_amount_minor,
        version = version + 1,
        updated_at = NOW()
    WHERE account_id = p_source_account_id;

    -- 5. Create or update intent
    INSERT INTO transfer_intents (
        transfer_id, direction, source_account_id, destination_account_id,
        amount_minor, currency, status
    ) VALUES (
        p_transfer_id, 'OUTGOING', p_source_account_id, p_dest_account_id,
        p_amount_minor, p_currency, 'PREPARED'
    );

    v_res := jsonb_build_object(
        'status', 'PREPARED',
        'transfer_id', p_transfer_id,
        'held_amount_minor', p_amount_minor
    );

    INSERT INTO command_inbox (command_id, transfer_id, command_type, payload_hash, result)
    VALUES (p_command_id, p_transfer_id, 'SOURCE_PREPARE', p_payload_hash, v_res);

    RETURN v_res;
END;
$$;

-- Stored procedure for destination prepare (acceptance of incoming obligation)
CREATE OR REPLACE FUNCTION destination_prepare(
    p_command_id VARCHAR(255),
    p_transfer_id UUID,
    p_source_account_id UUID,
    p_dest_account_id UUID,
    p_amount_minor BIGINT,
    p_currency VARCHAR(3),
    p_payload_hash VARCHAR(64)
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_existing_inbox RECORD;
    v_intent RECORD;
    v_status VARCHAR;
    v_acct_curr VARCHAR;
    v_res JSONB;
BEGIN
    SELECT result, payload_hash INTO v_existing_inbox
    FROM command_inbox WHERE command_id = p_command_id;
    IF FOUND THEN
        IF v_existing_inbox.payload_hash <> p_payload_hash THEN
            RAISE EXCEPTION 'Idempotency conflict on command %', p_command_id USING ERRCODE = '23505';
        END IF;
        RETURN v_existing_inbox.result;
    END IF;

    -- Check for cancellation tombstone
    SELECT status INTO v_intent FROM transfer_intents WHERE transfer_id = p_transfer_id;
    IF FOUND AND v_intent.status = 'CANCELLED' THEN
        v_res := jsonb_build_object(
            'status', 'REJECTED',
            'reason', 'Transfer previously cancelled by tombstone',
            'transfer_id', p_transfer_id
        );
        INSERT INTO command_inbox (command_id, transfer_id, command_type, payload_hash, result)
        VALUES (p_command_id, p_transfer_id, 'DEST_PREPARE', p_payload_hash, v_res);
        RETURN v_res;
    END IF;

    -- Verify destination account exists, is ACTIVE, and currency matches
    SELECT status, currency INTO v_status, v_acct_curr
    FROM ledger_accounts WHERE account_id = p_dest_account_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Destination account % not found', p_dest_account_id USING ERRCODE = '23503';
    END IF;

    IF v_status <> 'ACTIVE' THEN
        v_res := jsonb_build_object(
            'status', 'REJECTED',
            'reason', 'Destination account is ' || v_status,
            'transfer_id', p_transfer_id
        );
        INSERT INTO command_inbox (command_id, transfer_id, command_type, payload_hash, result)
        VALUES (p_command_id, p_transfer_id, 'DEST_PREPARE', p_payload_hash, v_res);
        RETURN v_res;
    END IF;

    IF v_acct_curr <> p_currency THEN
        v_res := jsonb_build_object(
            'status', 'REJECTED',
            'reason', 'Currency mismatch: account ' || v_acct_curr || ', transfer ' || p_currency,
            'transfer_id', p_transfer_id
        );
        INSERT INTO command_inbox (command_id, transfer_id, command_type, payload_hash, result)
        VALUES (p_command_id, p_transfer_id, 'DEST_PREPARE', p_payload_hash, v_res);
        RETURN v_res;
    END IF;

    -- Record accepted incoming intent
    INSERT INTO transfer_intents (
        transfer_id, direction, source_account_id, destination_account_id,
        amount_minor, currency, status
    ) VALUES (
        p_transfer_id, 'INCOMING', p_source_account_id, p_dest_account_id,
        p_amount_minor, p_currency, 'PREPARED'
    );

    v_res := jsonb_build_object(
        'status', 'PREPARED',
        'transfer_id', p_transfer_id
    );

    INSERT INTO command_inbox (command_id, transfer_id, command_type, payload_hash, result)
    VALUES (p_command_id, p_transfer_id, 'DEST_PREPARE', p_payload_hash, v_res);

    RETURN v_res;
END;
$$;

-- Stored procedure for source confirmation (settle outgoing: consume hold + post journal)
CREATE OR REPLACE FUNCTION source_confirm(
    p_command_id VARCHAR(255),
    p_transfer_id UUID,
    p_payload_hash VARCHAR(64)
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_existing_inbox RECORD;
    v_intent RECORD;
    v_hold RECORD;
    v_journal_id UUID := gen_random_uuid();
    v_clearing_id UUID := '00000000-0000-0000-0000-000000000002'::UUID;
    v_lines JSONB;
    v_res JSONB;
BEGIN
    SELECT result, payload_hash INTO v_existing_inbox
    FROM command_inbox WHERE command_id = p_command_id;
    IF FOUND THEN
        RETURN v_existing_inbox.result;
    END IF;

    SELECT * INTO v_intent FROM transfer_intents WHERE transfer_id = p_transfer_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Transfer intent % not found', p_transfer_id USING ERRCODE = '23503';
    END IF;

    IF v_intent.status = 'CONFIRMED' THEN
        RETURN jsonb_build_object('status', 'CONFIRMED', 'transfer_id', p_transfer_id);
    END IF;

    IF v_intent.status = 'CANCELLED' THEN
        RAISE EXCEPTION 'Cannot confirm CANCELLED transfer %', p_transfer_id USING ERRCODE = '55000';
    END IF;

    -- Consume hold
    SELECT * INTO v_hold FROM holds WHERE transfer_id = p_transfer_id FOR UPDATE;
    IF FOUND AND v_hold.status = 'ACTIVE' THEN
        UPDATE holds SET status = 'CONSUMED', updated_at = NOW() WHERE hold_id = v_hold.hold_id;
        UPDATE account_balances
        SET held_amount_minor = GREATEST(0, held_amount_minor - v_hold.amount_minor),
            version = version + 1,
            updated_at = NOW()
        WHERE account_id = v_hold.account_id;
    END IF;

    -- Post source settlement journal: Debit customer wallet, Credit clearing control
    v_lines := jsonb_build_array(
        jsonb_build_object('account_id', v_intent.source_account_id, 'side', 'DEBIT', 'amount_minor', v_intent.amount_minor),
        jsonb_build_object('account_id', v_clearing_id, 'side', 'CREDIT', 'amount_minor', v_intent.amount_minor)
    );

    PERFORM post_journal(
        v_journal_id,
        p_transfer_id,
        'SOURCE_SETTLE',
        v_intent.currency,
        p_command_id,
        'Cross-ledger source settlement',
        v_lines
    );

    UPDATE transfer_intents
    SET status = 'CONFIRMED', updated_at = NOW()
    WHERE transfer_id = p_transfer_id;

    v_res := jsonb_build_object(
        'status', 'CONFIRMED',
        'transfer_id', p_transfer_id,
        'journal_id', v_journal_id
    );

    INSERT INTO command_inbox (command_id, transfer_id, command_type, payload_hash, result)
    VALUES (p_command_id, p_transfer_id, 'SOURCE_CONFIRM', p_payload_hash, v_res);

    RETURN v_res;
END;
$$;

-- Stored procedure for destination confirmation (settle incoming: post destination journal)
CREATE OR REPLACE FUNCTION destination_confirm(
    p_command_id VARCHAR(255),
    p_transfer_id UUID,
    p_payload_hash VARCHAR(64)
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_existing_inbox RECORD;
    v_intent RECORD;
    v_journal_id UUID := gen_random_uuid();
    v_clearing_id UUID := '00000000-0000-0000-0000-000000000002'::UUID;
    v_lines JSONB;
    v_res JSONB;
BEGIN
    SELECT result, payload_hash INTO v_existing_inbox
    FROM command_inbox WHERE command_id = p_command_id;
    IF FOUND THEN
        RETURN v_existing_inbox.result;
    END IF;

    SELECT * INTO v_intent FROM transfer_intents WHERE transfer_id = p_transfer_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Transfer intent % not found', p_transfer_id USING ERRCODE = '23503';
    END IF;

    IF v_intent.status = 'CONFIRMED' THEN
        RETURN jsonb_build_object('status', 'CONFIRMED', 'transfer_id', p_transfer_id);
    END IF;

    IF v_intent.status = 'CANCELLED' THEN
        RAISE EXCEPTION 'Cannot confirm CANCELLED transfer %', p_transfer_id USING ERRCODE = '55000';
    END IF;

    -- Post destination settlement journal: Debit clearing control, Credit customer wallet
    v_lines := jsonb_build_array(
        jsonb_build_object('account_id', v_clearing_id, 'side', 'DEBIT', 'amount_minor', v_intent.amount_minor),
        jsonb_build_object('account_id', v_intent.destination_account_id, 'side', 'CREDIT', 'amount_minor', v_intent.amount_minor)
    );

    PERFORM post_journal(
        v_journal_id,
        p_transfer_id,
        'DESTINATION_SETTLE',
        v_intent.currency,
        p_command_id,
        'Cross-ledger destination settlement',
        v_lines
    );

    UPDATE transfer_intents
    SET status = 'CONFIRMED', updated_at = NOW()
    WHERE transfer_id = p_transfer_id;

    v_res := jsonb_build_object(
        'status', 'CONFIRMED',
        'transfer_id', p_transfer_id,
        'journal_id', v_journal_id
    );

    INSERT INTO command_inbox (command_id, transfer_id, command_type, payload_hash, result)
    VALUES (p_command_id, p_transfer_id, 'DEST_CONFIRM', p_payload_hash, v_res);

    RETURN v_res;
END;
$$;

-- Stored procedure for participant cancellation / tombstone
CREATE OR REPLACE FUNCTION apply_participant_cancel(
    p_command_id VARCHAR(255),
    p_transfer_id UUID,
    p_payload_hash VARCHAR(64)
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_existing_inbox RECORD;
    v_intent RECORD;
    v_hold RECORD;
    v_res JSONB;
BEGIN
    SELECT result, payload_hash INTO v_existing_inbox
    FROM command_inbox WHERE command_id = p_command_id;
    IF FOUND THEN
        RETURN v_existing_inbox.result;
    END IF;

    -- Check intent
    SELECT * INTO v_intent FROM transfer_intents WHERE transfer_id = p_transfer_id;
    IF FOUND THEN
        IF v_intent.status = 'CONFIRMED' THEN
            RAISE EXCEPTION 'Cannot cancel CONFIRMED transfer %', p_transfer_id USING ERRCODE = '55000';
        END IF;

        IF v_intent.direction = 'OUTGOING' THEN
            -- Release hold if active
            SELECT * INTO v_hold FROM holds WHERE transfer_id = p_transfer_id FOR UPDATE;
            IF FOUND AND v_hold.status = 'ACTIVE' THEN
                UPDATE holds SET status = 'RELEASED', updated_at = NOW() WHERE hold_id = v_hold.hold_id;
                UPDATE account_balances
                SET held_amount_minor = GREATEST(0, held_amount_minor - v_hold.amount_minor),
                    version = version + 1,
                    updated_at = NOW()
                WHERE account_id = v_hold.account_id;
            END IF;
        END IF;

        UPDATE transfer_intents
        SET status = 'CANCELLED', updated_at = NOW()
        WHERE transfer_id = p_transfer_id;
    ELSE
        -- Transfer not yet prepared: persist CANCELLED tombstone to reject delayed prepare
        INSERT INTO transfer_intents (
            transfer_id, direction, source_account_id, destination_account_id,
            amount_minor, currency, status
        ) VALUES (
            p_transfer_id, 'OUTGOING',
            '00000000-0000-0000-0000-000000000001'::UUID,
            '00000000-0000-0000-0000-000000000001'::UUID,
            1, 'INR', 'CANCELLED'
        );
    END IF;

    v_res := jsonb_build_object(
        'status', 'CANCELLED',
        'transfer_id', p_transfer_id
    );

    INSERT INTO command_inbox (command_id, transfer_id, command_type, payload_hash, result)
    VALUES (p_command_id, p_transfer_id, 'CANCEL', p_payload_hash, v_res);

    RETURN v_res;
END;
$$;

-- Permissions grants
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'ledgerguard_app') THEN
        GRANT SELECT, INSERT, UPDATE ON transfer_intents TO ledgerguard_app;
        GRANT SELECT, INSERT, UPDATE ON holds TO ledgerguard_app;
        GRANT SELECT, INSERT, UPDATE ON command_inbox TO ledgerguard_app;
        GRANT SELECT, INSERT, UPDATE ON participant_outbox TO ledgerguard_app;
        GRANT EXECUTE ON FUNCTION source_prepare TO ledgerguard_app;
        GRANT EXECUTE ON FUNCTION destination_prepare TO ledgerguard_app;
        GRANT EXECUTE ON FUNCTION source_confirm TO ledgerguard_app;
        GRANT EXECUTE ON FUNCTION destination_confirm TO ledgerguard_app;
        GRANT EXECUTE ON FUNCTION apply_participant_cancel TO ledgerguard_app;
    END IF;

    IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'ledgerguard_reporter') THEN
        GRANT SELECT ON transfer_intents TO ledgerguard_reporter;
        GRANT SELECT ON holds TO ledgerguard_reporter;
        GRANT SELECT ON command_inbox TO ledgerguard_reporter;
        GRANT SELECT ON participant_outbox TO ledgerguard_reporter;
    END IF;
END
$$;
