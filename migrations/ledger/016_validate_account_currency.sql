-- Validate the account-currency format constraint that 015 added NOT VALID, but only where every existing
-- row already conforms. Account currency is immutable (a trigger enforces it), so a migration never
-- rewrites legacy rows; where any remain, the constraint stays NOT VALID and still guards new rows.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM ledger_accounts WHERE currency !~ '^[A-Z]{3}$') THEN
        ALTER TABLE ledger_accounts VALIDATE CONSTRAINT ledger_accounts_currency_format;
    ELSE
        RAISE NOTICE 'ledger_accounts_currency_format left NOT VALID: legacy rows do not conform';
    END IF;
END $$;
