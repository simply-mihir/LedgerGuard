-- Declarative integrity the application already assumed (re-runnable; data checked before writing).

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'journal_headers_currency_format') THEN
        ALTER TABLE journal_headers ADD CONSTRAINT journal_headers_currency_format CHECK (currency ~ '^[A-Z]{3}$');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'local_transfers_currency_format') THEN
        ALTER TABLE local_transfers ADD CONSTRAINT local_transfers_currency_format CHECK (currency ~ '^[A-Z]{3}$');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'transfer_intents_currency_format') THEN
        ALTER TABLE transfer_intents ADD CONSTRAINT transfer_intents_currency_format CHECK (currency ~ '^[A-Z]{3}$');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'transfer_reversals_amount_positive') THEN
        ALTER TABLE transfer_reversals ADD CONSTRAINT transfer_reversals_amount_positive CHECK (amount_minor > 0);
    END IF;
    -- NOT VALID: enforced for every new/updated row; pre-existing rows are not rewritten (history is
    -- never edited). A development database may hold legacy rows that predate the rule.
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ledger_accounts_currency_format') THEN
        ALTER TABLE ledger_accounts ADD CONSTRAINT ledger_accounts_currency_format
            CHECK (currency ~ '^[A-Z]{3}$') NOT VALID;
    END IF;
END $$;
