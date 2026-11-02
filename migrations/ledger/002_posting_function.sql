-- Migration: 002_posting_function.sql
-- Description: Database-enforced atomic posting boundary, locking discipline, and permission grants

CREATE OR REPLACE FUNCTION post_journal(
    p_journal_id UUID,
    p_transfer_id UUID,
    p_operation_type VARCHAR(64),
    p_currency VARCHAR(3),
    p_correlation_id VARCHAR(128),
    p_description TEXT,
    p_lines JSONB
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_line_record RECORD;
    v_line_idx INT := 0;
    v_account_ids UUID[];
    v_total_debits BIGINT := 0;
    v_total_credits BIGINT := 0;
    v_account_record RECORD;
    
    -- In-memory state tracking per account
    v_posted_changes JSONB := '{}'::jsonb;
    v_cur_posted BIGINT;
    v_cur_held BIGINT;
    v_new_posted BIGINT;
    v_cur_seq BIGINT;
    v_new_seq BIGINT;
    v_delta BIGINT;
    v_acct_type VARCHAR;
    v_status VARCHAR;
BEGIN
    -- Validate currency
    IF p_currency IS NULL OR p_currency <> 'INR' THEN
        RAISE EXCEPTION 'Unsupported currency %; only INR is supported', p_currency
            USING ERRCODE = '22023';
    END IF;

    -- Validate minimum lines
    IF jsonb_array_length(p_lines) < 2 THEN
        RAISE EXCEPTION 'Journal must contain at least 2 lines; got %', jsonb_array_length(p_lines)
            USING ERRCODE = '23514';
    END IF;

    -- Collect and deduplicate account IDs
    SELECT ARRAY_AGG(DISTINCT (elem->>'account_id')::UUID)
    INTO v_account_ids
    FROM jsonb_array_elements(p_lines) elem;

    -- Acquire row-level locks on account_balances in deterministic account_id ASC order
    PERFORM 1
    FROM account_balances
    WHERE account_id = ANY(v_account_ids)
    ORDER BY account_id ASC
    FOR UPDATE;

    -- Validate balance balancing & amount bounds
    FOR v_line_record IN SELECT * FROM jsonb_to_recordset(p_lines) AS x(
        account_id UUID,
        side VARCHAR,
        amount_minor BIGINT
    )
    LOOP
        IF v_line_record.amount_minor <= 0 THEN
            RAISE EXCEPTION 'Posting amount must be strictly positive, got %', v_line_record.amount_minor
                USING ERRCODE = '23514';
        END IF;

        IF v_line_record.side = 'DEBIT' THEN
            v_total_debits := v_total_debits + v_line_record.amount_minor;
        ELSIF v_line_record.side = 'CREDIT' THEN
            v_total_credits := v_total_credits + v_line_record.amount_minor;
        ELSE
            RAISE EXCEPTION 'Invalid posting side %; expected DEBIT or CREDIT', v_line_record.side
                USING ERRCODE = '22023';
        END IF;
    END LOOP;

    IF v_total_debits <> v_total_credits THEN
        RAISE EXCEPTION 'Unbalanced journal: total debits (%) != total credits (%)', v_total_debits, v_total_credits
            USING ERRCODE = '23514';
    END IF;

    -- Insert journal header
    INSERT INTO journal_headers (
        journal_id,
        transfer_id,
        operation_type,
        currency,
        correlation_id,
        description,
        created_at
    ) VALUES (
        p_journal_id,
        p_transfer_id,
        p_operation_type,
        p_currency,
        p_correlation_id,
        p_description,
        NOW()
    );

    -- Apply lines and update balances
    FOR v_line_record IN SELECT * FROM jsonb_to_recordset(p_lines) AS x(
        account_id UUID,
        side VARCHAR,
        amount_minor BIGINT
    )
    LOOP
        v_line_idx := v_line_idx + 1;

        -- Load current account balance and metadata
        SELECT b.posted_balance_minor, b.held_amount_minor, b.account_sequence, a.account_type, a.status
        INTO v_cur_posted, v_cur_held, v_cur_seq, v_acct_type, v_status
        FROM account_balances b
        JOIN ledger_accounts a ON b.account_id = a.account_id
        WHERE b.account_id = v_line_record.account_id;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'Account % not found in ledger', v_line_record.account_id
                USING ERRCODE = '23503';
        END IF;

        IF v_status = 'CLOSED' THEN
            RAISE EXCEPTION 'Account % is CLOSED; postings are prohibited', v_line_record.account_id
                USING ERRCODE = '55000';
        END IF;

        -- Calculate balance change
        -- Customer liability accounts: credit increases, debit decreases
        -- Asset/Control accounts: debit increases, credit decreases
        IF v_acct_type = 'LIABILITY' THEN
            IF v_line_record.side = 'CREDIT' THEN
                v_delta := v_line_record.amount_minor;
            ELSE
                v_delta := -v_line_record.amount_minor;
            END IF;
        ELSE
            IF v_line_record.side = 'DEBIT' THEN
                v_delta := v_line_record.amount_minor;
            ELSE
                v_delta := -v_line_record.amount_minor;
            END IF;
        END IF;

        v_new_posted := v_cur_posted + v_delta;

        -- For customer wallets, posted balance and available balance can never be negative
        IF v_acct_type = 'LIABILITY' THEN
            IF v_new_posted < 0 THEN
                RAISE EXCEPTION 'Insufficient posted funds: account % balance would be % (min 0)',
                    v_line_record.account_id, v_new_posted
                    USING ERRCODE = '23514';
            END IF;
            IF (v_new_posted - v_cur_held) < 0 THEN
                RAISE EXCEPTION 'Insufficient available funds: account % available would be % (held %)',
                    v_line_record.account_id, (v_new_posted - v_cur_held), v_cur_held
                    USING ERRCODE = '23514';
            END IF;
        END IF;

        v_new_seq := v_cur_seq + 1;

        -- Insert immutable journal line
        INSERT INTO journal_lines (
            line_id,
            journal_id,
            line_no,
            account_id,
            side,
            amount_minor,
            account_sequence
        ) VALUES (
            gen_random_uuid(),
            p_journal_id,
            v_line_idx,
            v_line_record.account_id,
            v_line_record.side,
            v_line_record.amount_minor,
            v_new_seq
        );

        -- Update account_balances row atomically
        UPDATE account_balances
        SET posted_balance_minor = v_new_posted,
            account_sequence = v_new_seq,
            version = version + 1,
            updated_at = NOW()
        WHERE account_id = v_line_record.account_id;
    END LOOP;

    -- Record audit event
    INSERT INTO audit_events (
        actor,
        action,
        resource_id,
        new_state,
        correlation_id
    ) VALUES (
        'system',
        'POST_JOURNAL',
        p_journal_id::text,
        jsonb_build_object(
            'journal_id', p_journal_id,
            'operation_type', p_operation_type,
            'amount_minor', v_total_debits,
            'currency', p_currency
        ),
        p_correlation_id
    );

    RETURN jsonb_build_object(
        'journal_id', p_journal_id,
        'status', 'POSTED',
        'amount_minor', v_total_debits,
        'line_count', v_line_idx
    );
END;
$$;

-- Permissions management for application role immutability
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'ledgerguard_app') THEN
        -- Allow connecting & using schema
        GRANT USAGE ON SCHEMA public TO ledgerguard_app;

        -- Account read & create permissions
        GRANT SELECT, INSERT ON ledger_accounts TO ledgerguard_app;
        GRANT SELECT, INSERT ON account_balances TO ledgerguard_app;

        -- Posting execution permission
        GRANT EXECUTE ON FUNCTION post_journal TO ledgerguard_app;

        -- Explicitly revoke direct mutations on financial tables
        REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON journal_headers FROM ledgerguard_app;
        REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON journal_lines FROM ledgerguard_app;
        REVOKE UPDATE, DELETE, TRUNCATE ON ledger_accounts FROM ledgerguard_app;
        REVOKE UPDATE, DELETE, TRUNCATE ON account_balances FROM ledgerguard_app;
        REVOKE TRUNCATE ON ALL TABLES IN SCHEMA public FROM ledgerguard_app;

        -- Read access to journals for queries and statements
        GRANT SELECT ON journal_headers TO ledgerguard_app;
        GRANT SELECT ON journal_lines TO ledgerguard_app;
        GRANT SELECT, INSERT ON audit_events TO ledgerguard_app;
    END IF;

    IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'ledgerguard_reporter') THEN
        GRANT USAGE ON SCHEMA public TO ledgerguard_reporter;
        GRANT SELECT ON ALL TABLES IN SCHEMA public TO ledgerguard_reporter;
    END IF;
END
$$;
