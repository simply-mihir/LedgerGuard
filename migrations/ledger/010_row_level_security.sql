-- Forward migration: row-level security for customer-scoped read access.
--
-- Adds a NOLOGIN role, ledgerguard_customer_reader, that can only SELECT five tables and only the
-- rows belonging to one customer, chosen per transaction through the ledgerguard.customer_id
-- setting. With no (or an empty) setting it sees nothing: the policies fail closed.
--
-- Existing behaviour is preserved explicitly: enabling RLS makes every non-owner role with no
-- matching policy see zero rows, so ledgerguard_app and ledgerguard_reporter get an unrestricted
-- policy. Table owners (the migration/admin role, and so SECURITY DEFINER functions such as
-- post_journal) bypass RLS; FORCE is intentionally NOT set so posting and hash-chain verification
-- are unchanged. No posted history is read, rewritten or moved by this migration.

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'ledgerguard_customer_reader') THEN
        -- NOLOGIN: reachable only by SET ROLE from a role that was explicitly granted membership.
        CREATE ROLE ledgerguard_customer_reader NOLOGIN;
    END IF;
END
$$;

-- The customer this transaction is scoped to; NULL (no rows) when unset or empty.
-- A malformed value raises an error, which also fails closed.
CREATE OR REPLACE FUNCTION ledgerguard_scope_customer()
RETURNS UUID
LANGUAGE sql
STABLE
AS $$
    SELECT NULLIF(current_setting('ledgerguard.customer_id', true), '')::uuid
$$;

GRANT USAGE ON SCHEMA public TO ledgerguard_customer_reader;
GRANT EXECUTE ON FUNCTION ledgerguard_scope_customer() TO ledgerguard_customer_reader;
GRANT SELECT ON ledger_accounts, account_balances, journal_headers, journal_lines,
    balance_snapshots TO ledgerguard_customer_reader;

ALTER TABLE ledger_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE account_balances ENABLE ROW LEVEL SECURITY;
ALTER TABLE journal_headers ENABLE ROW LEVEL SECURITY;
ALTER TABLE journal_lines ENABLE ROW LEVEL SECURITY;
ALTER TABLE balance_snapshots ENABLE ROW LEVEL SECURITY;

-- Unrestricted policies for the existing runtime and reporting roles (no behaviour change).
DO $$
DECLARE
    t TEXT;
    r TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['ledger_accounts', 'account_balances', 'journal_headers',
                             'journal_lines', 'balance_snapshots'] LOOP
        FOREACH r IN ARRAY ARRAY['ledgerguard_app', 'ledgerguard_reporter'] LOOP
            IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = r) THEN
                EXECUTE format('DROP POLICY IF EXISTS %I ON %I', t || '_' || r || '_all', t);
                EXECUTE format(
                    'CREATE POLICY %I ON %I AS PERMISSIVE FOR ALL TO %I USING (true) WITH CHECK (true)',
                    t || '_' || r || '_all', t, r);
            END IF;
        END LOOP;
    END LOOP;
END
$$;

-- Customer-scoped, read-only policies.
DROP POLICY IF EXISTS ledger_accounts_customer_read ON ledger_accounts;
CREATE POLICY ledger_accounts_customer_read ON ledger_accounts
    FOR SELECT TO ledgerguard_customer_reader
    USING (customer_id IS NOT NULL AND customer_id = ledgerguard_scope_customer());

DROP POLICY IF EXISTS account_balances_customer_read ON account_balances;
CREATE POLICY account_balances_customer_read ON account_balances
    FOR SELECT TO ledgerguard_customer_reader
    USING (EXISTS (
        SELECT 1 FROM ledger_accounts a
        WHERE a.account_id = account_balances.account_id
          AND a.customer_id = ledgerguard_scope_customer()));

DROP POLICY IF EXISTS journal_lines_customer_read ON journal_lines;
CREATE POLICY journal_lines_customer_read ON journal_lines
    FOR SELECT TO ledgerguard_customer_reader
    USING (EXISTS (
        SELECT 1 FROM ledger_accounts a
        WHERE a.account_id = journal_lines.account_id
          AND a.customer_id = ledgerguard_scope_customer()));

-- A journal header is visible when at least one of its lines belongs to the customer; the other
-- party's lines stay hidden by the journal_lines policy.
DROP POLICY IF EXISTS journal_headers_customer_read ON journal_headers;
CREATE POLICY journal_headers_customer_read ON journal_headers
    FOR SELECT TO ledgerguard_customer_reader
    USING (EXISTS (
        SELECT 1 FROM journal_lines l
        JOIN ledger_accounts a ON a.account_id = l.account_id
        WHERE l.journal_id = journal_headers.journal_id
          AND a.customer_id = ledgerguard_scope_customer()));

DROP POLICY IF EXISTS balance_snapshots_customer_read ON balance_snapshots;
CREATE POLICY balance_snapshots_customer_read ON balance_snapshots
    FOR SELECT TO ledgerguard_customer_reader
    USING (EXISTS (
        SELECT 1 FROM ledger_accounts a
        WHERE a.account_id = balance_snapshots.account_id
          AND a.customer_id = ledgerguard_scope_customer()));
