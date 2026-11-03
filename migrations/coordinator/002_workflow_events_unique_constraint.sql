-- Migration: 002_workflow_events_unique_constraint.sql
-- Description: Enforce at-most-once workflow event recording per transfer and event type

-- 1. Deduplicate any existing duplicates deterministically, preserving the earliest event by created_at and event_id
DELETE FROM workflow_events
WHERE event_id IN (
    SELECT event_id
    FROM (
        SELECT event_id,
               ROW_NUMBER() OVER (
                   PARTITION BY transfer_id, event_type
                   ORDER BY created_at ASC, event_id ASC
               ) AS rn
        FROM workflow_events
    ) ranked
    WHERE ranked.rn > 1
);

-- 2. Add unique constraint on (transfer_id, event_type)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'uq_workflow_events_transfer_event'
    ) THEN
        ALTER TABLE workflow_events
            ADD CONSTRAINT uq_workflow_events_transfer_event
            UNIQUE (transfer_id, event_type);
    END IF;
END $$;
