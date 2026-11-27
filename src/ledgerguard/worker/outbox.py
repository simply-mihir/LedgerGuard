"""PostgreSQL transactional outbox claim and delivery tracking."""

from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from ledgerguard.db.pool import get_db_connection
from ledgerguard.observability import inject_trace_carrier, safe_span


def record_outbox_event(
    conn: Any,
    table_name: str,
    aggregate_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> UUID:
    """Insert an outbox event within an existing open database transaction."""
    enriched_payload = dict(payload)
    enriched_payload["_trace"] = inject_trace_carrier()
    with safe_span("outbox.enqueue", attributes={"transfer.id": aggregate_id, "operation.type": event_type}):
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                f"""
                INSERT INTO {table_name} (
                    aggregate_id, event_type, payload, attempts, next_attempt_at, created_at
                ) VALUES (%s, %s, %s, 0, NOW(), NOW())
                RETURNING outbox_id;
            """,
                (aggregate_id, event_type, Jsonb(enriched_payload)),
            )
            row = cur.fetchone()
            if not row:
                raise RuntimeError("Failed to insert outbox event")
            return UUID(str(row["outbox_id"]))


def claim_pending_outbox_events(
    db_url: str,
    table_name: str = "outbox_events",
    batch_size: int = 20,
    lock_duration_seconds: int = 15,
    aggregate_id: UUID | None = None,
) -> list[dict[str, Any]]:
    """Claim pending outbox events using FOR UPDATE SKIP LOCKED."""
    # The lease is computed by the database (``NOW() + interval``), the same clock that
    # ``next_attempt_at <= NOW()`` is evaluated against. Using this process's wall clock here would
    # let an app/DB clock difference turn a lease into an instant expiry (duplicate delivery) or a
    # long stall.
    with get_db_connection(db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            if aggregate_id:
                cur.execute(
                    f"""
                    SELECT outbox_id, aggregate_id, event_type, payload, attempts
                    FROM {table_name}
                    WHERE next_attempt_at <= NOW() AND delivered_at IS NULL AND aggregate_id = %s
                    ORDER BY next_attempt_at ASC
                    LIMIT %s
                    FOR UPDATE SKIP LOCKED;
                """,
                    (str(aggregate_id), batch_size),
                )
            else:
                cur.execute(
                    f"""
                    SELECT outbox_id, aggregate_id, event_type, payload, attempts
                    FROM {table_name}
                    WHERE next_attempt_at <= NOW() AND delivered_at IS NULL
                    ORDER BY next_attempt_at ASC
                    LIMIT %s
                    FOR UPDATE SKIP LOCKED;
                """,
                    (batch_size,),
                )
            events = cur.fetchall()

            if events:
                event_ids = [e["outbox_id"] for e in events]
                cur.execute(
                    f"""
                    UPDATE {table_name}
                    SET attempts = attempts + 1,
                        next_attempt_at = NOW() + make_interval(secs => %s)
                    WHERE outbox_id = ANY(%s);
                """,
                    (lock_duration_seconds, event_ids),
                )
        conn.commit()

    return [dict(e) for e in events]


def mark_outbox_delivered(
    db_url: str,
    outbox_id: UUID,
    table_name: str = "outbox_events",
) -> None:
    """Mark an outbox event as successfully delivered."""
    with get_db_connection(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE {table_name}
                SET delivered_at = NOW()
                WHERE outbox_id = %s;
            """,
                (outbox_id,),
            )
        conn.commit()


def mark_outbox_failed(
    db_url: str,
    outbox_id: UUID,
    retry_delay_seconds: int = 5,
    table_name: str = "outbox_events",
) -> None:
    """Reschedule an outbox event for retry after a backoff delay."""
    with get_db_connection(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE {table_name}
                SET next_attempt_at = NOW() + make_interval(secs => %s)
                WHERE outbox_id = %s;
            """,
                (retry_delay_seconds, outbox_id),
            )
        conn.commit()


OUTBOX_CHANNEL = "outbox_ready"


def wait_for_outbox_work(db_url: str, timeout_seconds: float) -> bool:
    """Block until a new outbox event is committed or ``timeout_seconds`` passes.

    Returns True when woken by a notification, False on timeout. A notification is only a hint:
    callers must still claim work from the table, and must keep polling on a timer because a
    notification sent while nobody listens (or across a server restart) is lost.
    """
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute(f"LISTEN {OUTBOX_CHANNEL}")
        for _ in conn.notifies(timeout=timeout_seconds, stop_after=1):
            return True
    return False
