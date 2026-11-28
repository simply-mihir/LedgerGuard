"""Try-Confirm-Cancel (TCC) orchestrator coordinating distributed transfers across independent ledgers."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from ledgerguard.coordinator.failpoints import (
    FailpointManager,
)
from ledgerguard.coordinator.failpoints import (
    failpoints as default_failpoints,
)
from ledgerguard.db.advisory import singleton
from ledgerguard.db.pool import get_db_connection
from ledgerguard.observability import extract_trace_context, inject_trace_carrier, safe_span
from ledgerguard.participant.workflow_handler import (
    handle_destination_confirm,
    handle_destination_prepare,
    handle_participant_cancel,
    handle_source_confirm,
    handle_source_prepare,
)
from ledgerguard.worker.coordinator_service import record_durable_decision

logger = logging.getLogger(__name__)


class OrchestrationError(Exception):
    """Base exception for TCC orchestration."""


def record_workflow_event(
    conn: Any,
    transfer_id: UUID,
    event_type: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Append an event to coordinator workflow_events audit table."""
    from psycopg.types.json import Jsonb

    enriched = dict(details or {})
    carrier = inject_trace_carrier()
    if carrier and "traceparent" in carrier:
        enriched["_traceparent"] = carrier["traceparent"]

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO workflow_events (transfer_id, event_type, details, created_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (transfer_id, event_type) DO NOTHING;
        """,
            (transfer_id, event_type, Jsonb(enriched)),
        )


def record_workflow_event_once(
    conn: Any,
    transfer_id: UUID,
    event_type: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Append an event to coordinator workflow_events audit table if not already recorded."""
    from psycopg.types.json import Jsonb

    enriched = dict(details or {})
    carrier = inject_trace_carrier()
    if carrier and "traceparent" in carrier:
        enriched["_traceparent"] = carrier["traceparent"]

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO workflow_events (transfer_id, event_type, details, created_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (transfer_id, event_type) DO NOTHING;
        """,
            (transfer_id, event_type, Jsonb(enriched)),
        )


def execute_two_phase_commit(
    coord_db_url: str,
    transfer_id: UUID,
    ledger_db_urls: dict[str, str],
    failpoint_mgr: FailpointManager | None = None,
) -> dict[str, Any]:
    """Execute or resume TCC orchestration for a distributed transfer.

    Guarantees:
    - Prepare phase reserves funds on source and checks destination viability.
    - Decision point records durable, immutable COMMIT or CANCEL before confirmation.
    - Post-COMMIT recovery ALWAYS recovers forward (never cancels or refunds).
    - Source settlement strictly precedes destination settlement.
    - Cancel-before-prepare and prepare rejections safely release source holds.
    """
    fp = failpoint_mgr or default_failpoints

    # 1. Fetch transfer details and existing decision from coordinator
    with get_db_connection(coord_db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT transfer_id, idempotency_key, source_account_id, destination_account_id,
                       amount_minor, currency, transfer_type, state, source_ledger_id, destination_ledger_id
                FROM transfers
                WHERE transfer_id = %s;
            """,
                (transfer_id,),
            )
            t = cur.fetchone()
            if not t:
                raise OrchestrationError(f"Transfer {transfer_id} not found.")

            cur.execute(
                """
                SELECT decision, decided_at
                FROM transfer_decisions
                WHERE transfer_id = %s;
            """,
                (transfer_id,),
            )
            dec_row = cur.fetchone()

    # Early return if transfer already reached a terminal state
    if t["state"] in ("SETTLED", "CANCELLED"):
        return {"transfer_id": str(transfer_id), "status": t["state"]}

    source_ledger_url = ledger_db_urls[t["source_ledger_id"]]
    dest_ledger_url = ledger_db_urls[t["destination_ledger_id"]]
    amount = int(t["amount_minor"])
    currency = str(t["currency"])
    source_acc = UUID(str(t["source_account_id"]))
    dest_acc = UUID(str(t["destination_account_id"]))

    # -----------------------------------------------------------------------
    # Case A: A durable decision already exists (Forward or Cancel Recovery)
    # -----------------------------------------------------------------------
    if dec_row:
        decision = dec_row["decision"]
        if decision == "COMMIT":
            # Recover forward: complete source confirm, then destination confirm
            logger.info("Forward recovering committed transfer %s", transfer_id)

            # Step A.1: Source Confirm
            handle_source_confirm(
                source_ledger_url,
                command_id=f"sc-{transfer_id}",
                transfer_id=transfer_id,
            )
            with get_db_connection(coord_db_url) as conn:
                record_workflow_event_once(
                    conn,
                    transfer_id,
                    "SOURCE_CONFIRMED",
                    {"ledger_id": t["source_ledger_id"], "role": "source", "step": "source_settlement"},
                )
                conn.commit()

            # Step A.2: Check failpoint between source confirm and dest confirm
            fp.check("FAIL_AFTER_SOURCE_CONFIRM_BEFORE_DEST_CONFIRM", transfer_id)

            # Step A.3: Destination Confirm
            handle_destination_confirm(
                dest_ledger_url,
                command_id=f"dc-{transfer_id}",
                transfer_id=transfer_id,
            )
            with get_db_connection(coord_db_url) as conn:
                record_workflow_event_once(
                    conn,
                    transfer_id,
                    "DESTINATION_CONFIRMED",
                    {"ledger_id": t["destination_ledger_id"], "role": "destination", "step": "destination_settlement"},
                )
                conn.commit()

            # Step A.4: Check failpoint after dest confirm reply
            fp.check("FAIL_AFTER_DEST_CONFIRM_REPLY", transfer_id)

            # Settle on coordinator
            with get_db_connection(coord_db_url) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE transfers
                        SET state = 'SETTLED', updated_at = NOW()
                        WHERE transfer_id = %s;
                    """,
                        (transfer_id,),
                    )
                record_workflow_event_once(conn, transfer_id, "TRANSFER_SETTLED", {"status": "SETTLED"})
                conn.commit()

            return {"transfer_id": str(transfer_id), "status": "SETTLED"}

        elif decision == "CANCEL":
            # Cancel recovery: ensure both sides cancel holds/intents
            handle_participant_cancel(
                source_ledger_url,
                command_id=f"sc-cancel-{transfer_id}",
                transfer_id=transfer_id,
                reason="Recovery of cancelled transfer",
            )
            with get_db_connection(coord_db_url) as conn:
                record_workflow_event_once(
                    conn,
                    transfer_id,
                    "SOURCE_CANCELLED",
                    {"ledger_id": t["source_ledger_id"], "role": "source", "step": "source_cancel"},
                )
                conn.commit()

            handle_participant_cancel(
                dest_ledger_url,
                command_id=f"dc-cancel-{transfer_id}",
                transfer_id=transfer_id,
                reason="Recovery of cancelled transfer",
            )
            with get_db_connection(coord_db_url) as conn:
                record_workflow_event_once(
                    conn,
                    transfer_id,
                    "DESTINATION_CANCELLED",
                    {"ledger_id": t["destination_ledger_id"], "role": "destination", "step": "destination_cancel"},
                )
                conn.commit()

            with get_db_connection(coord_db_url) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE transfers
                        SET state = 'CANCELLED', updated_at = NOW()
                        WHERE transfer_id = %s;
                    """,
                        (transfer_id,),
                    )
                record_workflow_event_once(conn, transfer_id, "TRANSFER_CANCELLED", {"status": "CANCELLED"})
                conn.commit()

            return {"transfer_id": str(transfer_id), "status": "CANCELLED"}

    # -----------------------------------------------------------------------
    # Case B: No decision recorded yet (Execute TCC from start)
    # -----------------------------------------------------------------------
    # Update state to PREPARING
    with get_db_connection(coord_db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE transfers
                SET state = 'PREPARING', updated_at = NOW()
                WHERE transfer_id = %s;
            """,
                (transfer_id,),
            )
        record_workflow_event_once(
            conn,
            transfer_id,
            "PHASE_PREPARE_STARTED",
            {"source_ledger_id": t["source_ledger_id"], "destination_ledger_id": t["destination_ledger_id"]},
        )
        conn.commit()

    # Step 1: Source Prepare (reserve funds and create active hold)
    sp_res = handle_source_prepare(
        source_ledger_url,
        command_id=f"sp-{transfer_id}",
        transfer_id=transfer_id,
        source_account_id=source_acc,
        destination_account_id=dest_acc,
        amount_minor=amount,
        currency=currency,
    )

    # Check failpoint: lost reply after source prepare committed
    fp.check("FAIL_AFTER_SOURCE_PREPARE_REPLY", transfer_id)

    if sp_res.get("status") == "REJECTED":
        reason = sp_res.get("reason", "Source prepare rejected")
        record_durable_decision(coord_db_url, transfer_id, "CANCEL", reason=reason)
        with get_db_connection(coord_db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE transfers
                    SET state = 'CANCELLED', updated_at = NOW()
                    WHERE transfer_id = %s;
                """,
                    (transfer_id,),
                )
            record_workflow_event_once(
                conn, transfer_id, "SOURCE_PREPARE_REJECTED", {"reason": reason}
            )
            conn.commit()
        return {"transfer_id": str(transfer_id), "status": "CANCELLED", "reason": reason}

    # Step 2: Destination Prepare (verify recipient viability & register incoming intent)
    dp_res = handle_destination_prepare(
        dest_ledger_url,
        command_id=f"dp-{transfer_id}",
        transfer_id=transfer_id,
        source_account_id=source_acc,
        destination_account_id=dest_acc,
        amount_minor=amount,
        currency=currency,
    )

    if dp_res.get("status") == "REJECTED":
        reason = dp_res.get("reason", "Destination prepare rejected")
        # Record CANCEL decision
        record_durable_decision(coord_db_url, transfer_id, "CANCEL", reason=reason)

        # Release source hold
        handle_participant_cancel(
            source_ledger_url,
            command_id=f"sc-cancel-{transfer_id}",
            transfer_id=transfer_id,
            reason=f"Destination rejected: {reason}",
        )

        with get_db_connection(coord_db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE transfers
                    SET state = 'CANCELLED', updated_at = NOW()
                    WHERE transfer_id = %s;
                """,
                    (transfer_id,),
                )
            record_workflow_event_once(
                conn, transfer_id, "DESTINATION_PREPARE_REJECTED", {"reason": reason}
            )
            conn.commit()

        return {"transfer_id": str(transfer_id), "status": "CANCELLED", "reason": reason}

    # -----------------------------------------------------------------------
    # Step 3: Decision Point (Both prepared -> COMMIT)
    # -----------------------------------------------------------------------
    record_durable_decision(
        coord_db_url, transfer_id, "COMMIT", reason="Both participants prepared successfully"
    )

    with get_db_connection(coord_db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE transfers
                SET state = 'COMMITTING', updated_at = NOW()
                WHERE transfer_id = %s;
            """,
                (transfer_id,),
            )
        record_workflow_event_once(conn, transfer_id, "DECISION_COMMITTED", {"decision": "COMMIT"})
        conn.commit()

    # Check failpoint: crash immediately after COMMIT recorded
    fp.check("FAIL_AFTER_COMMIT_BEFORE_SOURCE_CONFIRM", transfer_id)

    # -----------------------------------------------------------------------
    # Step 4: Source Settlement (Source Confirm)
    # -----------------------------------------------------------------------
    handle_source_confirm(
        source_ledger_url,
        command_id=f"sc-{transfer_id}",
        transfer_id=transfer_id,
    )
    with get_db_connection(coord_db_url) as conn:
        record_workflow_event_once(
            conn,
            transfer_id,
            "SOURCE_CONFIRMED",
            {"ledger_id": t["source_ledger_id"], "role": "source", "step": "source_settlement"},
        )
        conn.commit()

    # Check failpoint: crash after source settlement before destination settlement
    fp.check("FAIL_AFTER_SOURCE_CONFIRM_BEFORE_DEST_CONFIRM", transfer_id)

    # -----------------------------------------------------------------------
    # Step 5: Destination Settlement (Destination Confirm)
    # -----------------------------------------------------------------------
    handle_destination_confirm(
        dest_ledger_url,
        command_id=f"dc-{transfer_id}",
        transfer_id=transfer_id,
    )
    with get_db_connection(coord_db_url) as conn:
        record_workflow_event_once(
            conn,
            transfer_id,
            "DESTINATION_CONFIRMED",
            {"ledger_id": t["destination_ledger_id"], "role": "destination", "step": "destination_settlement"},
        )
        conn.commit()

    # Check failpoint: lost reply after destination confirm committed
    fp.check("FAIL_AFTER_DEST_CONFIRM_REPLY", transfer_id)

    # Transition transfer state to SETTLED
    with get_db_connection(coord_db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE transfers
                SET state = 'SETTLED', updated_at = NOW()
                WHERE transfer_id = %s;
            """,
                (transfer_id,),
            )
        record_workflow_event_once(conn, transfer_id, "TRANSFER_SETTLED", {"status": "SETTLED"})
        conn.commit()

    return {"transfer_id": str(transfer_id), "status": "SETTLED"}


def recover_pending_transfers(
    coord_db_url: str,
    ledger_db_urls: dict[str, str],
    transfer_id: UUID | None = None,
    min_age_seconds: float = 0.0,
) -> list[dict[str, Any]]:
    """Scan and recover in-flight or interrupted transfers.

    A global sweep (no ``transfer_id``) is a cluster-wide singleton: if another sweep holds the advisory
    lock this one returns immediately instead of duplicating its work. Recovery of one named transfer
    is not serialised here; it is idempotent through the durable decision.
    """
    if transfer_id is None:
        with singleton(coord_db_url, RECOVERY_SWEEP_LOCK) as acquired:
            if not acquired:
                return []
            return _recover_pending_transfers(coord_db_url, ledger_db_urls, None, min_age_seconds)
    return _recover_pending_transfers(coord_db_url, ledger_db_urls, transfer_id)


RECOVERY_SWEEP_LOCK = "ledgerguard:recovery-sweep"


def _recover_pending_transfers(
    coord_db_url: str,
    ledger_db_urls: dict[str, str],
    transfer_id: UUID | None,
    min_age_seconds: float = 0.0,
) -> list[dict[str, Any]]:
    results = []
    with get_db_connection(coord_db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            if transfer_id:
                cur.execute(
                    """
                    SELECT transfer_id, state
                    FROM transfers
                    WHERE transfer_id = %s;
                """,
                    (transfer_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT transfer_id, state
                    FROM transfers
                    WHERE state IN ('ACCEPTED', 'PREPARING', 'COMMITTING', 'CANCELLING')
                      AND updated_at <= NOW() - make_interval(secs => %s)
                    ORDER BY created_at ASC;
                """,
                    (min_age_seconds,),
                )
            pending = cur.fetchall()

    for row in pending:
        t_id = UUID(str(row["transfer_id"]))
        parent_ctx = None
        try:
            with get_db_connection(coord_db_url) as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        "SELECT details FROM workflow_events WHERE transfer_id = %s ORDER BY created_at ASC LIMIT 1;",
                        (t_id,),
                    )
                    ev = cur.fetchone()
                    if ev and isinstance(ev.get("details"), dict):
                        det = ev["details"]
                        tp = det.get("_traceparent")
                        trace_carrier = {"traceparent": tp} if tp else det.get("_trace")
                        parent_ctx = extract_trace_context(trace_carrier)
            with safe_span(
                "recovery.retry_transfer",
                attributes={"transfer.id": str(t_id), "recovery.flag": True, "state.before": row.get("state")},
                parent_context=parent_ctx,
            ):
                res = execute_two_phase_commit(coord_db_url, t_id, ledger_db_urls)
                results.append(res)
        except Exception as exc:
            logger.error("Error recovering transfer %s: %s", t_id, exc)

    return results
