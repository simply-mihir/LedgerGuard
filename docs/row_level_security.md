# Row-level security

Migration: `migrations/ledger/010_row_level_security.sql` (forward only, both ledgers).
Helper: `src/ledgerguard/db/customer_scope.py`. Tests: `tests/test_row_level_security.py`.

## What it enforces

A NOLOGIN role, `ledgerguard_customer_reader`, can `SELECT` only five tables and only rows that
belong to one customer, named per transaction:

| Table | Visible when |
|---|---|
| `ledger_accounts` | `customer_id` equals the scope (system accounts, with no customer, are never visible) |
| `account_balances`, `balance_snapshots` | the account belongs to the scope customer |
| `journal_lines` | the line's account belongs to the scope customer |
| `journal_headers` | at least one line of the journal belongs to the scope customer |

For a transfer between two customers each sees the shared journal header but only their own line;
the counterparty's line and the platform cash/clearing legs stay hidden. Every other table
(`audit_events`, the hash-chain head, outbox/inbox, holds, ...) is not granted at all, and the role
has no write privilege anywhere.

It **fails closed**: with the scope unset or empty every protected table returns zero rows, and a
malformed scope raises an error rather than matching anything.

## Existing behaviour is unchanged

Enabling RLS makes any non-owner role without a matching policy see zero rows, so
`ledgerguard_app` and `ledgerguard_reporter` get explicit unrestricted policies. Table owners
(including the `SECURITY DEFINER` `post_journal`) bypass RLS; `FORCE ROW LEVEL SECURITY` is
deliberately **not** set, so posting, hash-chain verification and reconciliation behave exactly as
before. No posted history is read, rewritten or moved by the migration.

## Using it

```python
with psycopg.connect(url) as conn:
    with customer_scoped_transaction(conn, customer_id):   # SET LOCAL ROLE + scoped setting
        rows = conn.execute("SELECT * FROM account_balances").fetchall()
```

`SET LOCAL` and `set_config(..., true)` end with the transaction, so a pooled connection cannot
carry a scope or the reduced role into its next use. The role is NOLOGIN: an operator must
`GRANT ledgerguard_customer_reader TO <trusted connector login>`. Migration `ledger/017` grants it to `ledgerguard_app` only.

## Limits — read these

* **Wired into one endpoint.** `GET /v1/customers/{customer_id}/accounts` reads each ledger through
  `customer_scoped_transaction` (query in `participant/customer_view.py`, which carries no customer filter of
  its own). `ledger/017` grants `ledgerguard_app` membership of the reader role so a transaction can drop to
  it. Other endpoints remain operator-level; there is still no customer login, so the endpoint is reached with
  the operator bearer token.
* **The scope is a session setting.** Anyone who can run arbitrary SQL as that role can re-scope
  itself (a test documents this). RLS here defends against bugs and SQL injection in the *query
  layer*, not against a malicious holder of a login granted the role. Grant membership only to
  trusted code.
* **Owners and superusers bypass RLS**, as does any role with `BYPASSRLS`. `post_journal` and the
  migration role are owners by design.
* Per-row policy checks add a join to scoped reads; no performance measurement was made.
* Coordinator-side tables (`customers`, transfers) are not covered.
