-- Forward migration: index hygiene found by the query-plan study (docs/query_plans.md).
--
-- Drops three redundant indexes (each is already served by a constraint-backed index) to cut write
-- amplification on the hottest write path, and adds the one missing index. Only indexes change:
-- no row, journal or hash is read, rewritten or moved.

-- (account_id, account_sequence) is identical to uq_account_sequence.
DROP INDEX IF EXISTS idx_journal_lines_account_seq;
-- (journal_id) is a prefix of uq_journal_line (journal_id, line_no).
DROP INDEX IF EXISTS idx_journal_lines_journal_id;
-- (transfer_id) duplicates the unique constraint transfer_intents_transfer_id_key.
DROP INDEX IF EXISTS idx_transfer_intents_transfer;

-- Historical balance reconstruction reads holds by account up to a point in time, including
-- released ones; the existing partial index only covers ACTIVE holds.
CREATE INDEX IF NOT EXISTS idx_holds_account_created ON holds (account_id, created_at);
