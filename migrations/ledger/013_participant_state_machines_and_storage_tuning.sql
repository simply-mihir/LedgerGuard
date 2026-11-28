-- Forward migration: database-enforced participant state machines and storage tuning.
--
-- Holds, transfer intents and account status changed only through stored procedures and application
-- code; nothing in the database stopped a CONSUMED hold from becoming ACTIVE again, a CONFIRMED
-- intent from being cancelled, or a CLOSED account from reopening. These triggers refuse those, and
-- freeze the facts that must never change after creation. No journal, hold or intent row is touched.

CREATE OR REPLACE FUNCTION enforce_hold_state_machine()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'ACTIVE' THEN
            RAISE EXCEPTION 'A hold must be created ACTIVE, not %', NEW.status USING ERRCODE = '55000';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.hold_id <> OLD.hold_id OR NEW.account_id <> OLD.account_id
       OR NEW.transfer_id <> OLD.transfer_id OR NEW.amount_minor <> OLD.amount_minor THEN
        RAISE EXCEPTION 'The account, transfer and amount of hold % are immutable', OLD.hold_id
            USING ERRCODE = '55000';
    END IF;
    IF NEW.status <> OLD.status AND NOT (OLD.status = 'ACTIVE' AND NEW.status IN ('CONSUMED', 'RELEASED')) THEN
        RAISE EXCEPTION 'Illegal hold transition % -> % for hold %', OLD.status, NEW.status, OLD.hold_id
            USING ERRCODE = '55000';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_hold_state_machine ON holds;
CREATE TRIGGER trg_hold_state_machine
    BEFORE INSERT OR UPDATE ON holds
    FOR EACH ROW EXECUTE FUNCTION enforce_hold_state_machine();

CREATE OR REPLACE FUNCTION enforce_intent_state_machine()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        -- PREPARED normally; CANCELLED is the tombstone written when a cancel arrives before a prepare.
        IF NEW.status NOT IN ('PREPARED', 'CANCELLED') THEN
            RAISE EXCEPTION 'A transfer intent must be created PREPARED or CANCELLED, not %', NEW.status
                USING ERRCODE = '55000';
        END IF;
        RETURN NEW;
    END IF;
    IF NEW.intent_id <> OLD.intent_id OR NEW.transfer_id <> OLD.transfer_id
       OR NEW.direction <> OLD.direction OR NEW.source_account_id <> OLD.source_account_id
       OR NEW.destination_account_id <> OLD.destination_account_id
       OR NEW.amount_minor <> OLD.amount_minor OR NEW.currency <> OLD.currency THEN
        RAISE EXCEPTION 'The facts of transfer intent % are immutable', OLD.intent_id USING ERRCODE = '55000';
    END IF;
    IF NEW.status <> OLD.status AND NOT (OLD.status = 'PREPARED' AND NEW.status IN ('CONFIRMED', 'CANCELLED')) THEN
        RAISE EXCEPTION 'Illegal intent transition % -> % for transfer %', OLD.status, NEW.status, OLD.transfer_id
            USING ERRCODE = '55000';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_intent_state_machine ON transfer_intents;
CREATE TRIGGER trg_intent_state_machine
    BEFORE INSERT OR UPDATE ON transfer_intents
    FOR EACH ROW EXECUTE FUNCTION enforce_intent_state_machine();

CREATE OR REPLACE FUNCTION enforce_account_state_machine()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.account_type <> OLD.account_type OR NEW.normal_side <> OLD.normal_side
       OR NEW.currency <> OLD.currency THEN
        RAISE EXCEPTION 'The type, normal side and currency of account % are immutable', OLD.account_id
            USING ERRCODE = '55000';
    END IF;
    IF OLD.status = 'CLOSED' AND NEW.status <> 'CLOSED' THEN
        RAISE EXCEPTION 'Account % is CLOSED and cannot be reopened', OLD.account_id USING ERRCODE = '55000';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_account_state_machine ON ledger_accounts;
CREATE TRIGGER trg_account_state_machine
    BEFORE UPDATE ON ledger_accounts
    FOR EACH ROW EXECUTE FUNCTION enforce_account_state_machine();

-- Storage tuning (metadata only). account_balances is updated on every posting; journal_chain_head is a
-- single row updated on every commit. Measured: fillfactor 90 gives 100% HOT updates (96.9% at the
-- default) at a smaller size than 80 (docs/data_integrity.md). Vacuum triggers on dead tuples, not on
-- 20% of the table. holds.status is a partial-index predicate, so its updates are never HOT.
ALTER TABLE account_balances SET (fillfactor = 90, autovacuum_vacuum_scale_factor = 0.02,
                                  autovacuum_vacuum_threshold = 50, autovacuum_analyze_scale_factor = 0.05);
ALTER TABLE journal_chain_head SET (autovacuum_vacuum_scale_factor = 0, autovacuum_vacuum_threshold = 50);
ALTER TABLE transfer_intents SET (fillfactor = 90, autovacuum_vacuum_scale_factor = 0.05,
                                  autovacuum_vacuum_threshold = 50);
ALTER TABLE holds SET (autovacuum_vacuum_scale_factor = 0.05, autovacuum_vacuum_threshold = 50);
ALTER TABLE participant_outbox SET (autovacuum_vacuum_scale_factor = 0.02, autovacuum_vacuum_threshold = 50);
