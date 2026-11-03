"""Participant internal workflow command handlers wrapping stored procedures."""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from ledgerguard.db.pool import get_db_connection
from ledgerguard.domain.idempotency import compute_payload_hash


def handle_source_prepare(
    db_url: str,
    command_id: str,
    transfer_id: UUID,
    source_account_id: UUID,
    dest_account_id: UUID | None = None,
    amount_minor: int = 0,
    currency: str = "INR",
    destination_account_id: UUID | None = None,
) -> dict[str, Any]:
    """Execute source participant prepare: reserve funds with durable hold."""
    target_dest = dest_account_id or destination_account_id
    if not target_dest:
        raise ValueError("Either dest_account_id or destination_account_id must be provided.")

    payload_hash = compute_payload_hash(
        {
            "command_id": command_id,
            "transfer_id": str(transfer_id),
            "source": str(source_account_id),
            "dest": str(target_dest),
            "amount_minor": amount_minor,
            "currency": currency,
        }
    )

    with get_db_connection(db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT source_prepare(
                    %s, %s, %s, %s, %s, %s, %s
                ) AS result;
            """,
                (
                    command_id,
                    transfer_id,
                    source_account_id,
                    target_dest,
                    amount_minor,
                    currency,
                    payload_hash,
                ),
            )
            row = cur.fetchone()
            result = row["result"] if row else {}
        conn.commit()

    return dict(result)


def handle_destination_prepare(
    db_url: str,
    command_id: str,
    transfer_id: UUID,
    source_account_id: UUID,
    dest_account_id: UUID | None = None,
    amount_minor: int = 0,
    currency: str = "INR",
    destination_account_id: UUID | None = None,
) -> dict[str, Any]:
    """Execute destination participant prepare: validate account and accept incoming intent."""
    target_dest = dest_account_id or destination_account_id
    if not target_dest:
        raise ValueError("Either dest_account_id or destination_account_id must be provided.")

    payload_hash = compute_payload_hash(
        {
            "command_id": command_id,
            "transfer_id": str(transfer_id),
            "source": str(source_account_id),
            "dest": str(target_dest),
            "amount_minor": amount_minor,
            "currency": currency,
        }
    )

    with get_db_connection(db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT destination_prepare(
                    %s, %s, %s, %s, %s, %s, %s
                ) AS result;
            """,
                (
                    command_id,
                    transfer_id,
                    source_account_id,
                    target_dest,
                    amount_minor,
                    currency,
                    payload_hash,
                ),
            )
            row = cur.fetchone()
            result = row["result"] if row else {}
        conn.commit()

    return dict(result)


def handle_source_confirm(
    db_url: str,
    command_id: str,
    transfer_id: UUID,
) -> dict[str, Any]:
    """Execute source confirmation: consume hold and post source settlement journal."""
    import psycopg

    payload_hash = compute_payload_hash(
        {
            "command_id": command_id,
            "transfer_id": str(transfer_id),
            "action": "SOURCE_CONFIRM",
        }
    )

    with get_db_connection(db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            try:
                cur.execute(
                    """
                    SELECT source_confirm(%s, %s, %s) AS result;
                """,
                    (command_id, transfer_id, payload_hash),
                )
                row = cur.fetchone()
                result = row["result"] if row else {}
                conn.commit()
            except psycopg.errors.UniqueViolation:
                conn.rollback()
                cur.execute(
                    """
                    SELECT result FROM command_inbox WHERE command_id = %s;
                """,
                    (command_id,),
                )
                row = cur.fetchone()
                result = row["result"] if row else {"status": "CONFIRMED", "transfer_id": str(transfer_id)}
                conn.commit()

    return dict(result)


def handle_destination_confirm(
    db_url: str,
    command_id: str,
    transfer_id: UUID,
) -> dict[str, Any]:
    """Execute destination confirmation: post destination settlement journal to credit recipient."""
    import psycopg

    payload_hash = compute_payload_hash(
        {
            "command_id": command_id,
            "transfer_id": str(transfer_id),
            "action": "DEST_CONFIRM",
        }
    )

    with get_db_connection(db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            try:
                cur.execute(
                    """
                    SELECT destination_confirm(%s, %s, %s) AS result;
                """,
                    (command_id, transfer_id, payload_hash),
                )
                row = cur.fetchone()
                result = row["result"] if row else {}
                conn.commit()
            except psycopg.errors.UniqueViolation:
                conn.rollback()
                cur.execute(
                    """
                    SELECT result FROM command_inbox WHERE command_id = %s;
                """,
                    (command_id,),
                )
                row = cur.fetchone()
                result = row["result"] if row else {"status": "CONFIRMED", "transfer_id": str(transfer_id)}
                conn.commit()

    return dict(result)


def handle_participant_cancel(
    db_url: str,
    command_id: str,
    transfer_id: UUID,
    reason: str | None = None,
) -> dict[str, Any]:
    """Execute participant cancellation: release hold or record cancellation tombstone."""
    import psycopg

    payload_hash = compute_payload_hash(
        {
            "command_id": command_id,
            "transfer_id": str(transfer_id),
            "action": "CANCEL",
            "reason": reason or "",
        }
    )

    with get_db_connection(db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            try:
                cur.execute(
                    """
                    SELECT apply_participant_cancel(%s, %s, %s) AS result;
                """,
                    (command_id, transfer_id, payload_hash),
                )
                row = cur.fetchone()
                result = row["result"] if row else {}
                conn.commit()
            except psycopg.errors.UniqueViolation:
                conn.rollback()
                cur.execute(
                    """
                    SELECT result FROM command_inbox WHERE command_id = %s;
                """,
                    (command_id,),
                )
                row = cur.fetchone()
                result = row["result"] if row else {"status": "CANCELLED", "transfer_id": str(transfer_id)}
                conn.commit()

    return dict(result)


def get_intent_status(db_url: str, transfer_id: UUID) -> dict[str, Any] | None:
    """Query current status of a transfer intent on a participant ledger."""
    with get_db_connection(db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT intent_id, transfer_id, direction, source_account_id,
                       destination_account_id, amount_minor, currency, status
                FROM transfer_intents
                WHERE transfer_id = %s;
            """,
                (transfer_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def get_hold_status(db_url: str, transfer_id: UUID) -> dict[str, Any] | None:
    """Query current status of an outgoing reservation hold on a participant ledger."""
    with get_db_connection(db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT hold_id, account_id, transfer_id, amount_minor, status
                FROM holds
                WHERE transfer_id = %s;
            """,
                (transfer_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
