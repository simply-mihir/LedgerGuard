"""PostgreSQL transactional outbox claim and delivery tracking."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from ledgerguard.db.pool import get_db_connection


def record_outbox_event(
    conn: Any,
    table_name: str,
    aggregate_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> UUID:
    """Insert an outbox event within an existing open database transaction."""
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            f"""
            INSERT INTO {table_name} (
                aggregate_id, event_type, payload, attempts, next_attempt_at, created_at
            ) VALUES (%s, %s, %s, 0, NOW(), NOW())
            RETURNING outbox_id;
        """,
            (aggregate_id, event_type, Jsonb(payload)),
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
    now = datetime.now(UTC)
    lease_until = now + timedelta(seconds=lock_duration_seconds)

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
                        next_attempt_at = %s
                    WHERE outbox_id = ANY(%s);
                """,
                    (lease_until, event_ids),
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
    retry_at = datetime.now(UTC) + timedelta(seconds=retry_delay_seconds)
    with get_db_connection(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE {table_name}
                SET next_attempt_at = %s
                WHERE outbox_id = %s;
            """,
                (retry_at, outbox_id),
            )
        conn.commit()
