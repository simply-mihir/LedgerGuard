-- Migration: 003_account_status_functions.sql
-- Description: Controlled stored procedure for account status transitions and closure checks

CREATE OR REPLACE FUNCTION update_account_status(
    p_account_id UUID,
    p_new_status VARCHAR(16),
    p_reason TEXT DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_cur_status VARCHAR(16);
    v_posted BIGINT;
    v_held BIGINT;
BEGIN
    SELECT a.status, b.posted_balance_minor, b.held_amount_minor
    INTO v_cur_status, v_posted, v_held
    FROM account_balances b
    JOIN ledger_accounts a ON b.account_id = a.account_id
    WHERE b.account_id = p_account_id
    FOR UPDATE OF b;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Account % not found', p_account_id USING ERRCODE = '23503';
    END IF;

    IF v_cur_status = 'CLOSED' THEN
        RAISE EXCEPTION 'Account % is already CLOSED; status cannot be changed', p_account_id USING ERRCODE = '55000';
    END IF;

    IF p_new_status = 'CLOSED' THEN
        IF v_posted <> 0 OR v_held <> 0 THEN
            RAISE EXCEPTION 'Cannot close account % with non-zero balance: posted=%, held=%',
                p_account_id, v_posted, v_held USING ERRCODE = '23514';
        END IF;
    END IF;

    UPDATE ledger_accounts
    SET status = p_new_status, updated_at = NOW()
    WHERE account_id = p_account_id;

    INSERT INTO audit_events (
        actor, action, resource_id, old_state, new_state
    ) VALUES (
        'system',
        'UPDATE_ACCOUNT_STATUS',
        p_account_id::text,
        jsonb_build_object('status', v_cur_status),
        jsonb_build_object('status', p_new_status, 'reason', p_reason)
    );

    RETURN jsonb_build_object(
        'account_id', p_account_id,
        'old_status', v_cur_status,
        'new_status', p_new_status
    );
END;
$$;

DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'ledgerguard_app') THEN
        GRANT EXECUTE ON FUNCTION update_account_status TO ledgerguard_app;
    END IF;
END
$$;
