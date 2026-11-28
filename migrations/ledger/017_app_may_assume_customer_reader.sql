-- Let the runtime role drop to the customer-reader role for one transaction (SET LOCAL ROLE), so API reads
-- can run under row-level security. Membership only ever *reduces* privilege for that transaction: the
-- reader can SELECT five tables under RLS and nothing else. Documented trust boundary: the scope is a
-- session setting, so this guards the query layer, not a malicious holder of the app login.
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'ledgerguard_app')
       AND EXISTS (SELECT FROM pg_roles WHERE rolname = 'ledgerguard_customer_reader') THEN
        GRANT ledgerguard_customer_reader TO ledgerguard_app;
    END IF;
END $$;
