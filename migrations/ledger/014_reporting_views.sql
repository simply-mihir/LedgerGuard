-- Reporting views for the read-only reporter role.
--
-- Views carry the definition of "balance" and "trial balance" in one place in the database instead of
-- every consumer re-deriving it. They are security_invoker, so the caller's own table privileges and
-- row-level-security policies apply (a view must never widen what its reader may see).

CREATE OR REPLACE VIEW v_trial_balance WITH (security_invoker = true) AS
SELECT h.currency,
       COALESCE(SUM(l.amount_minor) FILTER (WHERE l.side = 'DEBIT'), 0)::bigint  AS total_debit_minor,
       COALESCE(SUM(l.amount_minor) FILTER (WHERE l.side = 'CREDIT'), 0)::bigint AS total_credit_minor,
       (COALESCE(SUM(l.amount_minor) FILTER (WHERE l.side = 'DEBIT'), 0)
        - COALESCE(SUM(l.amount_minor) FILTER (WHERE l.side = 'CREDIT'), 0))::bigint AS imbalance_minor,
       COUNT(DISTINCT h.journal_id)::bigint AS journals,
       COUNT(*)::bigint AS lines
FROM journal_headers h
JOIN journal_lines l ON l.journal_id = h.journal_id
GROUP BY h.currency;

CREATE OR REPLACE VIEW v_account_balances WITH (security_invoker = true) AS
SELECT a.account_id, a.account_type, a.normal_side, a.currency, a.status,
       COALESCE(SUM(CASE WHEN l.side = a.normal_side THEN l.amount_minor ELSE -l.amount_minor END), 0)::bigint
           AS balance_minor,
       COUNT(l.line_id)::bigint AS line_count
FROM ledger_accounts a
LEFT JOIN journal_lines l ON l.account_id = a.account_id
GROUP BY a.account_id, a.account_type, a.normal_side, a.currency, a.status;

GRANT SELECT ON v_trial_balance, v_account_balances TO ledgerguard_reporter;
