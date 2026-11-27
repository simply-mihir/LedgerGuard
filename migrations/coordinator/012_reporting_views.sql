-- Reporting views for the read-only reporter role (security_invoker: the caller's privileges apply).

CREATE OR REPLACE VIEW v_transfer_state_summary WITH (security_invoker = true) AS
SELECT t.state, t.currency,
       COUNT(*)::bigint AS transfers,
       COALESCE(SUM(t.amount_minor), 0)::bigint AS amount_minor,
       MIN(t.created_at) AS oldest_created_at
FROM transfers t
GROUP BY t.state, t.currency;

CREATE OR REPLACE VIEW v_open_transfers WITH (security_invoker = true) AS
SELECT t.transfer_id, t.state, t.transfer_type, t.amount_minor, t.currency,
       t.source_ledger_id, t.destination_ledger_id, t.attention_required, t.attention_reason,
       t.created_at, t.updated_at,
       EXTRACT(EPOCH FROM (NOW() - t.created_at))::bigint AS age_seconds
FROM transfers t
WHERE t.state IN ('ACCEPTED', 'PREPARING', 'COMMITTING', 'CANCELLING');

GRANT SELECT ON v_transfer_state_summary, v_open_transfers TO ledgerguard_reporter;
