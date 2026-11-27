"""Create a coordinator transfer exactly once per idempotency key, even under concurrency.

The database (trigger + unique claim, migration coordinator/010) is the arbiter: of N concurrent
inserts carrying one key exactly one commits; the others fail with a unique violation and *adopt*
the winner's transfer instead of creating their own. Adopting is safe because transfer execution
is idempotent and forward-recoverable.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, Literal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from ledgerguard.db.pool import get_db_connection
from ledgerguard.domain.idempotency import IdempotencyConflictError

Disposition = Literal["created", "adopted", "same_id"]

_INSERT = """
    INSERT INTO transfers (
        transfer_id, idempotency_key, source_account_id, destination_account_id,
        amount_minor, currency, transfer_type, state, source_ledger_id, destination_ledger_id
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'ACCEPTED', %s, %s)
    ON CONFLICT (transfer_id) DO NOTHING
    RETURNING transfer_id, state, amount_minor, currency
"""

_BY_KEY = """
    SELECT t.transfer_id, t.state, t.amount_minor, t.currency,
           t.source_account_id, t.destination_account_id
    FROM transfer_idempotency_claims c
    JOIN transfers t ON t.transfer_id = c.transfer_id
    WHERE c.idempotency_key = %s
"""

_BY_ID = """
    SELECT transfer_id, state, amount_minor, currency, source_account_id, destination_account_id
    FROM transfers WHERE transfer_id = %s
"""


def insert_or_adopt_transfer(
    coord_db_url: str,
    *,
    transfer_id: UUID,
    idempotency_key: str,
    source_account_id: UUID,
    destination_account_id: UUID,
    amount_minor: int,
    currency: str,
    transfer_type: str,
    source_ledger_id: str,
    destination_ledger_id: str,
    on_created: Callable[[psycopg.Connection], None] | None = None,
) -> tuple[dict[str, Any], Disposition]:
    """Return ``(transfer_row, disposition)``.

    * ``"created"`` - this caller's insert won; ``on_created`` ran in the same transaction (used
      for the outbox event). Only this caller should drive the transfer.
    * ``"adopted"`` - a *different* request already owns the key; wait for it (see
      :func:`wait_for_outcome`) instead of executing the transfer a second time concurrently.
    * ``"same_id"`` - the caller retried its own ``transfer_id``; it may safely resume execution.

    A key reused with a different payload raises :class:`IdempotencyConflictError`.
    """
    params = (transfer_id, idempotency_key, source_account_id, destination_account_id,
              amount_minor, currency, transfer_type, source_ledger_id, destination_ledger_id)
    with get_db_connection(coord_db_url) as conn:
        try:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(_INSERT, params)
                row = cur.fetchone()
            if row is not None and on_created is not None:
                on_created(conn)
            conn.commit()
            if row is not None:
                return dict(row), "created"
        except psycopg.errors.UniqueViolation:
            conn.rollback()  # another request already owns this key; adopt its transfer below

        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(_BY_ID, (transfer_id,))
            existing = cur.fetchone()
            disposition: Disposition = "same_id"
            if existing is None:
                cur.execute(_BY_KEY, (idempotency_key,))
                existing = cur.fetchone()
                disposition = "adopted"
        conn.commit()

    if existing is None:  # pragma: no cover - the claim must exist once a unique violation fired
        raise RuntimeError(f"idempotency key {idempotency_key!r} is claimed but its transfer is missing")
    if (existing["source_account_id"] != source_account_id
            or existing["destination_account_id"] != destination_account_id
            or int(existing["amount_minor"]) != amount_minor
            or existing["currency"] != currency):
        raise IdempotencyConflictError(
            f"Idempotency conflict: key '{idempotency_key}' reused with different payload."
        )
    row_out = {k: existing[k] for k in ("transfer_id", "state", "amount_minor", "currency")}
    return row_out, disposition


_TERMINAL = ("SETTLED", "CANCELLED", "REJECTED")


def wait_for_outcome(coord_db_url: str, transfer_id: UUID, timeout_s: float = 15.0,
                     poll_s: float = 0.05) -> dict[str, Any]:
    """Wait for the owner of an adopted transfer to finish it; never executes anything itself.

    Returns ``{"status", "reason"}``. If the transfer is still in flight at the deadline the
    current state is returned (the client may retry with the same key; the worker's recovery
    sweep keeps driving it), so a slow owner cannot make this call hang forever.
    """
    deadline = time.monotonic() + timeout_s
    while True:
        with get_db_connection(coord_db_url) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT t.state, d.reason FROM transfers t "
                    "LEFT JOIN transfer_decisions d ON d.transfer_id = t.transfer_id "
                    "WHERE t.transfer_id = %s", (transfer_id,))
                row = cur.fetchone()
            conn.commit()
        if row is None:  # pragma: no cover - adopted transfers exist
            raise RuntimeError(f"transfer {transfer_id} vanished while waiting")
        if row["state"] in _TERMINAL or time.monotonic() >= deadline:
            reason = row["reason"] if row["state"] == "CANCELLED" else None
            return {"status": row["state"], "reason": reason}
        time.sleep(poll_s)


__all__ = ["Disposition", "insert_or_adopt_transfer", "wait_for_outcome"]
