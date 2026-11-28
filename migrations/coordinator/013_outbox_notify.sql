-- Wake consumers when outbox work appears, instead of making them poll.
--
-- NOTIFY is transactional: it is delivered only if (and when) the inserting transaction commits, so a
-- consumer is never woken for work that was rolled back. The payload is deliberately empty - a
-- notification is a hint, never the source of truth. Consumers must still claim work from the table
-- (FOR UPDATE SKIP LOCKED) and keep a timed poll as a fallback, because notifications are lost if no
-- one is listening or the server restarts.

CREATE OR REPLACE FUNCTION notify_outbox_ready() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    PERFORM pg_notify('outbox_ready', '');
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS outbox_events_notify ON outbox_events;
CREATE TRIGGER outbox_events_notify
    AFTER INSERT ON outbox_events
    FOR EACH STATEMENT EXECUTE FUNCTION notify_outbox_ready();
