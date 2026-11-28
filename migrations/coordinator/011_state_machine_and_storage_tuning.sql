-- Forward migration: database-enforced transfer state machine, immutable decisions, storage tuning.
--
-- Until now the legal transfer transitions lived only in application code, and the runtime role may
-- UPDATE the row. These triggers make the database refuse an illegal transition (for example a
-- SETTLED transfer set back to ACCEPTED, or a committing transfer cancelled) and tie each decided
-- state to the durable decision, mirroring the TLA+ specification (decision monotonicity, commit /
-- cancel exclusivity). No existing row is read, rewritten or moved.

CREATE TABLE IF NOT EXISTS transfer_state_transitions (
    from_state VARCHAR(16) NOT NULL,
    to_state   VARCHAR(16) NOT NULL,
    PRIMARY KEY (from_state, to_state)
);

INSERT INTO transfer_state_transitions (from_state, to_state) VALUES
    ('ACCEPTED',   'PREPARING'),
    ('ACCEPTED',   'COMMITTING'),
    ('ACCEPTED',   'CANCELLING'),
    ('ACCEPTED',   'CANCELLED'),
    ('ACCEPTED',   'REJECTED'),
    ('PREPARING',  'COMMITTING'),
    ('PREPARING',  'CANCELLING'),
    ('PREPARING',  'CANCELLED'),
    ('PREPARING',  'REJECTED'),
    ('COMMITTING', 'SETTLED'),
    ('CANCELLING', 'CANCELLED')
ON CONFLICT DO NOTHING;

GRANT SELECT ON transfer_state_transitions TO ledgerguard_app, ledgerguard_reporter;

CREATE OR REPLACE FUNCTION enforce_transfer_state_machine()
RETURNS TRIGGER AS $$
DECLARE
    v_decision VARCHAR(16);
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.state <> 'ACCEPTED' THEN
            RAISE EXCEPTION 'A transfer must be created in state ACCEPTED, not %', NEW.state
                USING ERRCODE = '55000';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.state = OLD.state THEN
        RETURN NEW;  -- an update of some other column (attention flag, refunded amount, ...)
    END IF;

    IF NOT EXISTS (SELECT 1 FROM transfer_state_transitions
                   WHERE from_state = OLD.state AND to_state = NEW.state) THEN
        RAISE EXCEPTION 'Illegal transfer state transition % -> % for transfer %',
            OLD.state, NEW.state, NEW.transfer_id USING ERRCODE = '55000';
    END IF;

    IF NEW.state IN ('COMMITTING', 'SETTLED', 'CANCELLING', 'CANCELLED') THEN
        SELECT decision INTO v_decision FROM transfer_decisions WHERE transfer_id = NEW.transfer_id;
        IF NEW.state IN ('COMMITTING', 'SETTLED') AND v_decision IS DISTINCT FROM 'COMMIT' THEN
            RAISE EXCEPTION 'Transfer % cannot become % without a durable COMMIT decision (found %)',
                NEW.transfer_id, NEW.state, COALESCE(v_decision, 'none') USING ERRCODE = '55000';
        END IF;
        IF NEW.state IN ('CANCELLING', 'CANCELLED') AND v_decision IS DISTINCT FROM 'CANCEL' THEN
            RAISE EXCEPTION 'Transfer % cannot become % without a durable CANCEL decision (found %)',
                NEW.transfer_id, NEW.state, COALESCE(v_decision, 'none') USING ERRCODE = '55000';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_transfer_state_machine ON transfers;
CREATE TRIGGER trg_transfer_state_machine
    BEFORE INSERT OR UPDATE OF state ON transfers
    FOR EACH ROW EXECUTE FUNCTION enforce_transfer_state_machine();

-- A durable decision never changes once made (decision monotonicity), whoever holds UPDATE.
CREATE OR REPLACE FUNCTION reject_decision_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'A durable transfer decision is immutable (transfer %)', OLD.transfer_id
        USING ERRCODE = '55000';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_immutable_transfer_decisions ON transfer_decisions;
CREATE TRIGGER trg_immutable_transfer_decisions
    BEFORE UPDATE ON transfer_decisions
    FOR EACH ROW EXECUTE FUNCTION reject_decision_update();

-- Storage tuning (metadata only; existing pages are not rewritten). Measured on a scratch table
-- (docs/data_integrity.md): fillfactor 90 gave 100% HOT updates against 96.9% at the default, with a
-- smaller table than fillfactor 80, so 90 is used. autovacuum fires on dead tuples sooner than the
-- 20%-of-table default. transfers.state is a partial-index predicate and outbox_events.next_attempt_at is
-- indexed, so updates of those columns can never be HOT whatever the fillfactor; only vacuum helps.
ALTER TABLE transfers SET (fillfactor = 90, autovacuum_vacuum_scale_factor = 0.05,
                           autovacuum_vacuum_threshold = 50, autovacuum_analyze_scale_factor = 0.05);
ALTER TABLE outbox_events SET (autovacuum_vacuum_scale_factor = 0.02, autovacuum_vacuum_threshold = 50);
ALTER TABLE operator_sessions SET (autovacuum_vacuum_scale_factor = 0.05, autovacuum_vacuum_threshold = 50);
