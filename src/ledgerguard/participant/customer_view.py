"""A customer's own accounts and balances, read through PostgreSQL row-level security.

The query carries no customer filter of its own, on purpose: the database scopes the session to one
customer, so a mistake or an injected predicate here still cannot reach another customer's rows
(see ``db/customer_scope.py`` and ``docs/row_level_security.md``).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from ledgerguard.db.customer_scope import customer_scoped_transaction


def list_customer_accounts(db_url: str, customer_id: UUID) -> list[dict[str, Any]]:
    with psycopg.connect(db_url, row_factory=dict_row) as conn:
        with customer_scoped_transaction(conn, customer_id):
            rows = conn.execute(
                "SELECT a.account_id, a.currency, a.status, a.name, "
                "       b.posted_balance_minor, b.held_amount_minor, "
                "       b.posted_balance_minor - b.held_amount_minor AS available_balance_minor "
                "FROM ledger_accounts a JOIN account_balances b USING (account_id) "
                "ORDER BY a.created_at, a.account_id"
            ).fetchall()
    return [dict(r) for r in rows]
