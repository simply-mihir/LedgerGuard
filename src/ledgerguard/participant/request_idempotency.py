"""Database-enforced request idempotency for single-ledger writes (funding, cash-out, account creation).

The claim row and the write share one transaction, so:

* two concurrent requests with the same key serialise on the primary key; the second waits for the
  first to finish and then replays its stored result instead of writing again;
* a request that fails and rolls back leaves no claim, so it can be retried;
* reusing a key with a different payload is a conflict, never a silent replay.
"""

from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from ledgerguard.domain.idempotency import IdempotencyConflictError, compute_payload_hash

FUNDING = "FUNDING"
CASH_OUT = "CASH_OUT"
CREATE_ACCOUNT = "CREATE_ACCOUNT"


def claim(conn: Any, scope: str, key: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    """Claim ``(scope, key)`` inside the caller's transaction.

    Returns ``None`` when this request now owns the key and must perform the write, then call
    :func:`complete`. Returns the stored result when an earlier request already finished it.
    Raises :class:`IdempotencyConflictError` when the key was used for a different payload.
    """
    request_hash = compute_payload_hash(payload)
    cur = conn.execute(
        "INSERT INTO request_idempotency (scope, idempotency_key, request_hash, result) "
        "VALUES (%s, %s, %s, 'null'::jsonb) ON CONFLICT (scope, idempotency_key) DO NOTHING "
        "RETURNING 1",
        (scope, key, request_hash),
    )
    if cur.fetchone() is not None:
        return None
    stored = conn.execute(
        "SELECT request_hash, result FROM request_idempotency WHERE scope = %s AND idempotency_key = %s",
        (scope, key),
    ).fetchone()
    stored_hash, stored_result = (stored["request_hash"], stored["result"]) if isinstance(stored, dict) \
        else (stored[0], stored[1])
    if stored_hash != request_hash:
        raise IdempotencyConflictError(
            f"Idempotency-Key {key!r} was already used for a different {scope} request.")
    return dict(stored_result)


def complete(conn: Any, scope: str, key: str, result: dict[str, Any]) -> None:
    conn.execute(
        "UPDATE request_idempotency SET result = %s WHERE scope = %s AND idempotency_key = %s",
        (Jsonb(result), scope, key),
    )
