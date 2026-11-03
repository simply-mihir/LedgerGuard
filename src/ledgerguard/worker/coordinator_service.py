"""Coordinator workflow state transitions, durable decisions, and outbox integration."""

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from ledgerguard.db.pool import get_db_connection
from ledgerguard.worker.outbox import record_outbox_event


class CoordinatorError(Exception):
    """Base exception for coordinator state transition errors."""

    pass


class IncompatibleDecisionError(CoordinatorError):
    """Raised when an attempt is made to overwrite an immutable coordinator decision."""

    pass


def create_coordinator_transfer(
    coord_db_url: str,
    transfer_id: UUID,
    idempotency_key: str,
    source_account_id: UUID,
    destination_account_id: UUID,
    source_ledger_id: str,
    destination_ledger_id: str,
    amount_minor: int,
    currency: str = "INR",
    transfer_type: str = "CROSS_LEDGER",
) -> dict[str, Any]:
    """Persist a new transfer request in ACCEPTED state with an initial outbox task atomically."""
    with get_db_connection(coord_db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            # Check for existing transfer with same idempotency key
            cur.execute(
                """
                SELECT transfer_id, state, amount_minor, currency
                FROM transfers
                WHERE idempotency_key = %s;
            """,
                (idempotency_key,),
            )
            existing = cur.fetchone()
            if existing:
                return dict(existing)

            # Insert transfer record
            cur.execute(
                """
                INSERT INTO transfers (
                    transfer_id, idempotency_key, source_account_id,
                    destination_account_id, amount_minor, currency,
                    transfer_type, state, source_ledger_id, destination_ledger_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'ACCEPTED', %s, %s)
                RETURNING transfer_id, state, amount_minor, currency;
            """,
                (
                    transfer_id,
                    idempotency_key,
                    source_account_id,
                    destination_account_id,
                    amount_minor,
                    currency,
                    transfer_type,
                    source_ledger_id,
                    destination_ledger_id,
                ),
            )
            row = cur.fetchone()
            if not row:
                raise CoordinatorError("Failed to initiate transfer; row was not returned.")
            transfer_dict = dict(row)

            # Record outbox event for workflow worker to begin prepare phase
            record_outbox_event(
                conn,
                table_name="outbox_events",
                aggregate_id=str(transfer_id),
                event_type="DISPATCH_PREPARE",
                payload={
                    "transfer_id": str(transfer_id),
                    "source_account_id": str(source_account_id),
                    "destination_account_id": str(destination_account_id),
                    "source_ledger_id": source_ledger_id,
                    "destination_ledger_id": destination_ledger_id,
                    "amount_minor": amount_minor,
                    "currency": currency,
                },
            )
        conn.commit()

    return transfer_dict


def record_durable_decision(
    coord_db_url: str,
    transfer_id: UUID,
    decision: str,  # 'COMMIT' or 'CANCEL'
    reason: str | None = None,
) -> str:
    """Atomically record the durable decision under row lock.

    Guarantees that COMMIT and CANCEL are strictly mutually exclusive and immutable.
    """
    if decision not in ("COMMIT", "CANCEL"):
        raise ValueError(f"Invalid decision '{decision}'; expected COMMIT or CANCEL.")

    with get_db_connection(coord_db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            # 1. Lock transfer row
            cur.execute(
                """
                SELECT transfer_id, state, source_ledger_id, destination_ledger_id,
                       amount_minor, currency, source_account_id, destination_account_id
                FROM transfers
                WHERE transfer_id = %s
                FOR UPDATE;
            """,
                (transfer_id,),
            )
            t_row = cur.fetchone()
            if not t_row:
                raise CoordinatorError(f"Transfer {transfer_id} not found.")

            # 2. Check existing decision
            cur.execute(
                """
                SELECT decision, decided_at
                FROM transfer_decisions
                WHERE transfer_id = %s;
            """,
                (transfer_id,),
            )
            existing_decision = cur.fetchone()

            if existing_decision:
                existing_val = existing_decision["decision"]
                if existing_val != decision:
                    raise IncompatibleDecisionError(
                        f"Transfer {transfer_id} decision is already {existing_val}; cannot change to {decision}."
                    )
                # Idempotent re-entry
                return str(existing_val)

            # 3. Insert immutable decision
            cur.execute(
                """
                INSERT INTO transfer_decisions (
                    transfer_id, decision, decision_version, reason, decided_at
                ) VALUES (%s, %s, 1, %s, NOW());
            """,
                (transfer_id, decision, reason),
            )

            new_state = "COMMITTING" if decision == "COMMIT" else "CANCELLING"
            cur.execute(
                """
                UPDATE transfers
                SET state = %s, updated_at = NOW()
                WHERE transfer_id = %s;
            """,
                (new_state, transfer_id),
            )

            # Record workflow event
            cur.execute(
                """
                INSERT INTO workflow_events (
                    transfer_id, event_type, details
                ) VALUES (%s, 'DECISION_MADE', %s)
                ON CONFLICT (transfer_id, event_type) DO NOTHING;
            """,
                (transfer_id, Jsonb({"decision": decision, "reason": reason})),
            )

            # Emit outbox event for next phase
            next_event_type = "DISPATCH_CONFIRM" if decision == "COMMIT" else "DISPATCH_CANCEL"
            record_outbox_event(
                conn,
                table_name="outbox_events",
                aggregate_id=str(transfer_id),
                event_type=next_event_type,
                payload={
                    "transfer_id": str(transfer_id),
                    "decision": decision,
                    "source_ledger_id": t_row["source_ledger_id"],
                    "destination_ledger_id": t_row["destination_ledger_id"],
                    "amount_minor": t_row["amount_minor"],
                    "currency": t_row["currency"],
                },
            )
        conn.commit()

    return decision


def update_transfer_terminal_state(
    coord_db_url: str,
    transfer_id: UUID,
    final_state: str,  # 'SETTLED' or 'CANCELLED'
) -> None:
    """Transition a transfer to its terminal state."""
    with get_db_connection(coord_db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE transfers
                SET state = %s, attention_required = FALSE, updated_at = NOW()
                WHERE transfer_id = %s;
            """,
                (final_state, transfer_id),
            )
        conn.commit()


def flag_transfer_attention(
    coord_db_url: str,
    transfer_id: UUID,
    reason: str,
) -> None:
    """Flag a transfer as requiring operator attention without corrupting its state."""
    with get_db_connection(coord_db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE transfers
                SET attention_required = TRUE, attention_reason = %s, updated_at = NOW()
                WHERE transfer_id = %s;
            """,
                (reason, transfer_id),
            )
        conn.commit()
