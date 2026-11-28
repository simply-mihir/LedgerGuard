"""Customer-scoped read access enforced by PostgreSQL row-level security.

Inside :func:`customer_scoped_transaction` the session drops to the NOLOGIN role
``ledgerguard_customer_reader`` and names one customer. The database then returns only that
customer's accounts, balances, journal lines, journal headers and balance snapshots, and nothing
else, even if the SQL that follows is wrong or attacker-influenced.

Trust boundary: the scope is a session setting, so whoever can run arbitrary SQL as that role can
change it. This protects against bugs and injection in the *query layer*; it does not protect
against a malicious holder of a login that has been granted the role. Grant membership only to a
trusted connector (see docs/row_level_security.md).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import UUID

import psycopg

CUSTOMER_READER_ROLE = "ledgerguard_customer_reader"


@contextmanager
def customer_scoped_transaction(
    conn: psycopg.Connection[Any], customer_id: UUID
) -> Iterator[psycopg.Connection[Any]]:
    """Run one transaction as the customer reader, scoped to ``customer_id``.

    ``SET LOCAL`` and ``set_config(..., true)`` last only until the transaction ends, so a pooled
    connection can never carry a scope (or the reduced role) into its next use.
    """
    if not isinstance(customer_id, UUID):
        raise TypeError("customer_id must be a UUID")
    with conn.transaction():
        conn.execute(f"SET LOCAL ROLE {CUSTOMER_READER_ROLE}")
        conn.execute("SELECT set_config('ledgerguard.customer_id', %s, true)", (str(customer_id),))
        yield conn


__all__ = ["CUSTOMER_READER_ROLE", "customer_scoped_transaction"]
