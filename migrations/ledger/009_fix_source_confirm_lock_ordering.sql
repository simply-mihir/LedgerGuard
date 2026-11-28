-- Forward migration: Fix lock-order inversion in source_confirm between customer account and clearing account

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

    -- Lock hold row first
    SELECT * INTO v_hold FROM holds WHERE transfer_id = p_transfer_id FOR UPDATE;

    -- Acquire account_balances locks in strict account_id ASC order across BOTH source and clearing
    -- before mutating held_amount_minor, matching post_journal() lock order and preventing
    -- opposite-direction deadlocks with destination_confirm().
    PERFORM 1
    FROM account_balances
    WHERE account_id = ANY(
        ARRAY[
            COALESCE(v_hold.account_id, v_intent.source_account_id),
            v_clearing_id
        ]
    )
    ORDER BY account_id ASC
    FOR UPDATE;

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
