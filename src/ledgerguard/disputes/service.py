"""Compensating refund and chargeback/dispute workflow services."""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from ledgerguard.coordinator.transfer_coordinator import submit_coordinator_transfer
from ledgerguard.db.pool import get_db_connection
from ledgerguard.domain.idempotency import IdempotencyConflictError, compute_payload_hash
from ledgerguard.domain.money import AmountPaise
from ledgerguard.observability import amount_bucket, safe_span


class DisputeState(StrEnum):
    """Canonical chargeback/dispute lifecycle states."""

    OPENED = "OPENED"
    EVIDENCE_PENDING = "EVIDENCE_PENDING"
    UNDER_REVIEW = "UNDER_REVIEW"
    PROVISIONAL_HOLD = "PROVISIONAL_HOLD"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMPENSATION_PENDING = "COMPENSATION_PENDING"
    RESOLVED = "RESOLVED"


_ALLOWED_TRANSITIONS: dict[DisputeState, set[DisputeState]] = {
    DisputeState.OPENED: {DisputeState.EVIDENCE_PENDING, DisputeState.UNDER_REVIEW, DisputeState.REJECTED},
    DisputeState.EVIDENCE_PENDING: {DisputeState.UNDER_REVIEW, DisputeState.PROVISIONAL_HOLD, DisputeState.REJECTED},
    DisputeState.UNDER_REVIEW: {DisputeState.PROVISIONAL_HOLD, DisputeState.APPROVED, DisputeState.REJECTED},
    DisputeState.PROVISIONAL_HOLD: {DisputeState.APPROVED, DisputeState.REJECTED},
    DisputeState.APPROVED: {DisputeState.COMPENSATION_PENDING, DisputeState.RESOLVED},
    DisputeState.COMPENSATION_PENDING: {DisputeState.RESOLVED},
    DisputeState.REJECTED: {DisputeState.RESOLVED},
    DisputeState.RESOLVED: set(),
}


class RefundLimitExceededError(Exception):
    """Raised when refund amount exceeds remaining eligible transfer amount."""


class DisputeTransitionError(Exception):
    """Raised on invalid dispute state transitions."""


def issue_refund(
    coord_db_url: str,
    ledger_db_urls: dict[str, str],
    *,
    original_transfer_id: UUID,
    amount: AmountPaise,
    idempotency_key: str,
    reason: str = "customer_refund",
    actor: str = "operator",
) -> dict[str, Any]:
    """Issue a full or partial compensating refund from destination back to source."""
    payload_hash = compute_payload_hash(
        {
            "original_transfer_id": str(original_transfer_id),
            "amount_minor": amount.paise,
            "reason": reason,
        }
    )

    with safe_span(
        "disputes.issue_refund",
        attributes={
            "transfer.id": str(original_transfer_id),
            "operation.type": "REFUND",
            "amount.bucket": amount_bucket(amount.paise),
        },
    ):
        with get_db_connection(coord_db_url) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT * FROM transfer_refunds WHERE idempotency_key = %s;",
                    (idempotency_key,),
                )
                existing = cur.fetchone()
                if existing:
                    if existing["payload_hash"] != payload_hash:
                        raise IdempotencyConflictError("Refund idempotency key reused with different payload.")
                    return {
                        "refund_id": str(existing["refund_id"]),
                        "original_transfer_id": str(existing["original_transfer_id"]),
                        "refund_transfer_id": str(existing["refund_transfer_id"]),
                        "amount_minor": int(existing["amount_minor"]),
                        "status": "SETTLED",
                        "duplicate_ignored": True,
                    }

                cur.execute(
                    """
                    SELECT transfer_id, state, amount_minor, refunded_amount_minor,
                           source_account_id, destination_account_id, currency
                    FROM transfers
                    WHERE transfer_id = %s
                    FOR UPDATE;
                    """,
                    (original_transfer_id,),
                )
                tx = cur.fetchone()
                if not tx:
                    raise ValueError(f"Original transfer {original_transfer_id} not found.")
                if tx["state"] != "SETTLED":
                    raise RefundLimitExceededError(f"Transfer {original_transfer_id} is {tx['state']}, not SETTLED.")

                eligible = int(tx["amount_minor"]) - int(tx["refunded_amount_minor"])
                if amount.paise > eligible:
                    raise RefundLimitExceededError(
                        f"Refund {amount.paise} exceeds eligible remaining amount {eligible}."
                    )

                refund_tx_id = uuid4()
                refund_id = uuid4()
                # Reserve eligible amount optimistically under row lock before executing compensating transfer
                cur.execute(
                    """
                    UPDATE transfers
                    SET refunded_amount_minor = refunded_amount_minor + %s, updated_at = NOW()
                    WHERE transfer_id = %s;
                    """,
                    (amount.paise, original_transfer_id),
                )
                cur.execute(
                    """
                    INSERT INTO transfer_refunds (
                        refund_id, original_transfer_id, refund_transfer_id,
                        idempotency_key, payload_hash, amount_minor, reason, actor
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                    """,
                    (
                        refund_id,
                        original_transfer_id,
                        refund_tx_id,
                        idempotency_key,
                        payload_hash,
                        amount.paise,
                        reason,
                        actor,
                    ),
                )
            conn.commit()

        # Execute compensating transfer from original destination -> original source
        try:
            comp_res = submit_coordinator_transfer(
                coord_db_url,
                ledger_db_urls,
                idempotency_key=f"refund-tx-{refund_id}",
                source_account_id=UUID(str(tx["destination_account_id"])),
                destination_account_id=UUID(str(tx["source_account_id"])),
                amount=amount,
                currency=str(tx["currency"]),
                transfer_id=refund_tx_id,
            )
        except Exception:
            # Roll back reserved refunded_amount_minor if compensating transfer was rejected before commit
            with get_db_connection(coord_db_url) as rconn:
                with rconn.cursor() as rcur:
                    rcur.execute(
                        """
                        UPDATE transfers
                        SET refunded_amount_minor = GREATEST(0, refunded_amount_minor - %s), updated_at = NOW()
                        WHERE transfer_id = %s;
                        """,
                        (amount.paise, original_transfer_id),
                    )
                    rcur.execute("DELETE FROM transfer_refunds WHERE refund_id = %s;", (refund_id,))
                rconn.commit()
            raise

        return {
            "refund_id": str(refund_id),
            "original_transfer_id": str(original_transfer_id),
            "refund_transfer_id": str(refund_tx_id),
            "amount_minor": amount.paise,
            "cumulative_refunded_minor": int(tx["refunded_amount_minor"]) + amount.paise,
            "status": comp_res.get("status", "SETTLED"),
            "duplicate_ignored": False,
        }


def open_dispute(
    coord_db_url: str,
    *,
    transfer_id: UUID,
    amount: AmountPaise,
    reason_code: str,
    actor: str,
    evidence_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Open a new chargeback/dispute on a settled transfer."""
    dispute_id = uuid4()
    meta = evidence_metadata or {}
    with get_db_connection(coord_db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT transfer_id, state, amount_minor FROM transfers WHERE transfer_id = %s;",
                (transfer_id,),
            )
            tx = cur.fetchone()
            if not tx:
                raise ValueError(f"Transfer {transfer_id} not found.")
            if tx["state"] != "SETTLED":
                raise DisputeTransitionError(f"Cannot dispute transfer in state {tx['state']}.")
            if amount.paise > int(tx["amount_minor"]):
                raise RefundLimitExceededError("Dispute amount exceeds original transfer amount.")

            cur.execute(
                """
                INSERT INTO disputes (
                    dispute_id, transfer_id, state, amount_minor, reason_code,
                    evidence_metadata, created_by
                ) VALUES (%s, %s, 'OPENED', %s, %s, %s, %s)
                RETURNING *;
                """,
                (dispute_id, transfer_id, amount.paise, reason_code, Jsonb(meta), actor),
            )
            row = cur.fetchone()
            cur.execute(
                """
                INSERT INTO dispute_events (
                    dispute_id, from_state, to_state, actor, reason_code, evidence_metadata
                ) VALUES (%s, NULL, 'OPENED', %s, %s, %s);
                """,
                (dispute_id, actor, reason_code, Jsonb(meta)),
            )
        conn.commit()
    assert row is not None
    return dict(row)


def transition_dispute(
    coord_db_url: str,
    ledger_db_urls: dict[str, str],
    *,
    dispute_id: UUID,
    to_state: DisputeState,
    actor: str,
    reason_code: str | None = None,
    evidence_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Transition a dispute through its governed state machine and execute compensation on approval."""
    with get_db_connection(coord_db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM disputes WHERE dispute_id = %s FOR UPDATE;", (dispute_id,))
            d = cur.fetchone()
            if not d:
                raise ValueError(f"Dispute {dispute_id} not found.")
            cur_state = DisputeState(str(d["state"]))
            if to_state not in _ALLOWED_TRANSITIONS[cur_state]:
                raise DisputeTransitionError(f"Invalid transition {cur_state} -> {to_state}")

            decided_by = actor if to_state in (DisputeState.APPROVED, DisputeState.REJECTED) else d["decided_by"]
            cur.execute(
                """
                UPDATE disputes
                SET state = %s, decided_by = %s, updated_at = NOW()
                WHERE dispute_id = %s;
                """,
                (to_state.value, decided_by, dispute_id),
            )
            cur.execute(
                """
                INSERT INTO dispute_events (
                    dispute_id, from_state, to_state, actor, reason_code, evidence_metadata
                ) VALUES (%s, %s, %s, %s, %s, %s);
                """,
                (
                    dispute_id,
                    cur_state.value,
                    to_state.value,
                    actor,
                    reason_code or d["reason_code"],
                    Jsonb(evidence_metadata or {}),
                ),
            )
        conn.commit()

    # On APPROVED, automatically trigger compensating refund & mark RESOLVED
    if to_state == DisputeState.APPROVED:
        refund_res = issue_refund(
            coord_db_url,
            ledger_db_urls,
            original_transfer_id=UUID(str(d["transfer_id"])),
            amount=AmountPaise(int(d["amount_minor"])),
            idempotency_key=f"dispute-comp-{dispute_id}",
            reason=f"chargeback:{d['reason_code']}",
            actor=actor,
        )
        with get_db_connection(coord_db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE disputes
                    SET state = 'RESOLVED', compensation_transfer_id = %s, updated_at = NOW()
                    WHERE dispute_id = %s;
                    """,
                    (UUID(refund_res["refund_transfer_id"]), dispute_id),
                )
                cur.execute(
                    """
                    INSERT INTO dispute_events (
                        dispute_id, from_state, to_state, actor, reason_code, evidence_metadata
                    ) VALUES (%s, 'APPROVED', 'RESOLVED', %s, %s, %s);
                    """,
                    (
                        dispute_id,
                        actor,
                        d["reason_code"],
                        Jsonb({"compensation_transfer_id": refund_res["refund_transfer_id"]}),
                    ),
                )
            conn.commit()

    return get_dispute_detail(coord_db_url, dispute_id)


def get_dispute_detail(coord_db_url: str, dispute_id: UUID) -> dict[str, Any]:
    """Return dispute record with full immutable event timeline."""
    with get_db_connection(coord_db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM disputes WHERE dispute_id = %s;", (dispute_id,))
            d = cur.fetchone()
            if not d:
                raise ValueError(f"Dispute {dispute_id} not found.")
            cur.execute(
                "SELECT * FROM dispute_events WHERE dispute_id = %s ORDER BY created_at ASC;",
                (dispute_id,),
            )
            events = [dict(r) for r in cur.fetchall()]
    res = dict(d)
    res["events"] = events
    return res


def list_disputes(coord_db_url: str, limit: int = 50) -> list[dict[str, Any]]:
    """List recent disputes."""
    with get_db_connection(coord_db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM disputes ORDER BY created_at DESC LIMIT %s;", (limit,))
            return [dict(r) for r in cur.fetchall()]
