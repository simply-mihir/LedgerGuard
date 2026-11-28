-- Declarative integrity the application already assumed. Each constraint is added only if absent so the
-- migration is re-runnable; existing data was checked clean before this was written.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'transfers_currency_format') THEN
        ALTER TABLE transfers ADD CONSTRAINT transfers_currency_format CHECK (currency ~ '^[A-Z]{3}$');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'account_directory_currency_format') THEN
        ALTER TABLE account_directory ADD CONSTRAINT account_directory_currency_format CHECK (currency ~ '^[A-Z]{3}$');
    END IF;
    -- A transfer can never have been refunded for more than it moved, whatever the application does.
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'transfers_refund_within_amount') THEN
        ALTER TABLE transfers ADD CONSTRAINT transfers_refund_within_amount
            CHECK (refunded_amount_minor <= amount_minor);
    END IF;
END $$;
