"""Deterministic, rule-based explainable recovery diagnostic engine."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from ledgerguard.config import settings
from ledgerguard.db.pool import get_db_connection


class RecoveryDiagnosticInput(BaseModel):
    """Authoritative state inputs collected from Coordinator and Participant Ledgers."""

    transfer_id: str
    transfer_state: str
    decision: str | None = None
    source_ledger_id: str = "ledger-1"
    destination_ledger_id: str = "ledger-2"
    source_intent_status: str | None = None
    destination_intent_status: str | None = None
    source_hold_status: str | None = None
    source_confirmed: bool = False
    destination_confirmed: bool = False
    outbox_pending_count: int = 0
    retry_count: int = 0
    next_retry_at: str | None = None
    last_error: str | None = None
    reachable_databases: dict[str, bool] = Field(
        default_factory=lambda: {"coordinator": True, "ledger-1": True, "ledger-2": True}
    )
    reconciliation_findings: list[str] = Field(default_factory=list)


class RecoveryExplanation(BaseModel):
    """Deterministic explanation of why a transfer is in its current state and what happens next."""

    transfer_id: str
    classification: str
    current_state: str
    reason: str
    safety_implication: str
    next_action: str
    responsible_component: str
    retry_schedule: str
    blocking_dependency: str | None = None
    operator_action_required: bool = False
    evidence_references: list[str] = Field(default_factory=list)


def explain_transfer_recovery(inp: RecoveryDiagnosticInput) -> RecoveryExplanation:
    """Evaluate deterministic rules to explain unresolved or terminal transfer state.

    Unknown state combinations return UNCLASSIFIED_STATE rather than inventing an explanation.
    """
    evidence = [
        f"transfer:{inp.transfer_id}:state={inp.transfer_state}",
        f"decision={inp.decision or 'NONE'}",
        f"source_intent={inp.source_intent_status or 'NONE'}",
        f"dest_intent={inp.destination_intent_status or 'NONE'}",
        f"source_hold={inp.source_hold_status or 'NONE'}",
        f"source_confirmed={inp.source_confirmed}",
        f"dest_confirmed={inp.destination_confirmed}",
    ]
    if inp.reconciliation_findings:
        evidence.extend([f"recon:{f}" for f in inp.reconciliation_findings])

    retry_sched = (
        f"attempts={inp.retry_count}, next_retry={inp.next_retry_at}"
        if inp.next_retry_at or inp.retry_count
        else "immediate_on_worker_poll"
    )

    # 1. Contradictory / corrupted state detection
    if inp.decision == "COMMIT" and inp.transfer_state in ("CANCELLING", "CANCELLED"):
        return RecoveryExplanation(
            transfer_id=inp.transfer_id,
            classification="CONTRADICTORY_STATE_DETECTED",
            current_state=inp.transfer_state,
            reason="Contradiction: durable COMMIT decision exists alongside CANCELLING/CANCELLED transfer state.",
            safety_implication="Violates invariant I6 (durable COMMIT cannot revert to CANCEL).",
            next_action="Halt automated mutation and escalate to dual-control audit investigation.",
            responsible_component="coordinator",
            retry_schedule="halted",
            blocking_dependency="manual_audit_resolution",
            operator_action_required=True,
            evidence_references=evidence,
        )

    if inp.decision == "CANCEL" and inp.transfer_state in ("COMMITTING", "SETTLED"):
        return RecoveryExplanation(
            transfer_id=inp.transfer_id,
            classification="CONTRADICTORY_STATE_DETECTED",
            current_state=inp.transfer_state,
            reason="Contradiction: durable CANCEL decision exists alongside COMMITTING/SETTLED transfer state.",
            safety_implication="Violates invariants I7 and I9 (cancelled transfer must never commit or settle).",
            next_action="Halt automated mutation and run full cross-ledger reconciliation.",
            responsible_component="coordinator",
            retry_schedule="halted",
            blocking_dependency="manual_audit_resolution",
            operator_action_required=True,
            evidence_references=evidence,
        )

    if inp.transfer_state == "SETTLED" and inp.source_hold_status == "ACTIVE":
        return RecoveryExplanation(
            transfer_id=inp.transfer_id,
            classification="CONTRADICTORY_STATE_DETECTED",
            current_state=inp.transfer_state,
            reason="Contradiction: transfer is SETTLED but source hold remains ACTIVE.",
            safety_implication="Customer available balance remains locked despite settlement.",
            next_action="Run reconciliation and inspect source_confirm journal/hold state.",
            responsible_component=inp.source_ledger_id,
            retry_schedule="halted",
            blocking_dependency=inp.source_ledger_id,
            operator_action_required=True,
            evidence_references=evidence,
        )

    # 2. Partial reachability check
    unreachable = [db for db, ok in inp.reachable_databases.items() if not ok]
    if unreachable and inp.transfer_state not in ("SETTLED", "CANCELLED"):
        dep = ", ".join(sorted(unreachable))
        safety = (
            "The COMMIT decision is durable; transfer cannot be cancelled or refunded."
            if inp.decision == "COMMIT"
            else "Transfer progress is paused until unreachable databases recover."
        )
        return RecoveryExplanation(
            transfer_id=inp.transfer_id,
            classification="PARTIAL_REACHABILITY_BLOCKED",
            current_state=inp.transfer_state,
            reason=f"Required database(s) unreachable ({dep}); current state is {inp.transfer_state} with decision={inp.decision or 'NONE'}.",
            safety_implication=safety,
            next_action=f"Wait for {dep} to become reachable, then run forward recovery.",
            responsible_component=dep,
            retry_schedule=retry_sched,
            blocking_dependency=dep,
            operator_action_required=False,
            evidence_references=evidence,
        )

    # 3. Terminal states
    if inp.transfer_state == "SETTLED" and inp.decision == "COMMIT":
        return RecoveryExplanation(
            transfer_id=inp.transfer_id,
            classification="SETTLED_COMPLETE",
            current_state="SETTLED",
            reason="Durable COMMIT decision executed both source_confirm and destination_confirm cleanly.",
            safety_implication="Funds settled with zero residual holds and zero clearing imbalance.",
            next_action="No recovery action required.",
            responsible_component="none",
            retry_schedule="complete",
            operator_action_required=False,
            evidence_references=evidence,
        )

    if inp.transfer_state == "CANCELLED" and inp.decision in ("CANCEL", None):
        return RecoveryExplanation(
            transfer_id=inp.transfer_id,
            classification="CANCELLED_TOMBSTONED",
            current_state="CANCELLED",
            reason="Transfer cancelled before COMMIT; source hold released and cancellation tombstone recorded.",
            safety_implication="Delayed prepare commands will be rejected by the tombstone (invariant I10).",
            next_action="No recovery action required.",
            responsible_component="none",
            retry_schedule="complete",
            operator_action_required=False,
            evidence_references=evidence,
        )

    # 4. COMMITTING forward recovery states
    if inp.transfer_state == "COMMITTING" and inp.decision == "COMMIT":
        if not inp.source_confirmed:
            return RecoveryExplanation(
                transfer_id=inp.transfer_id,
                classification="COMMITTED_AWAITING_SOURCE_CONFIRM",
                current_state="COMMITTING",
                reason="The COMMIT decision is durable. Source confirmation has not yet been acknowledged.",
                safety_implication="The transfer cannot be cancelled or refunded; source hold remains reserved.",
                next_action=f"Retry SOURCE_CONFIRM on {inp.source_ledger_id} via forward recovery worker.",
                responsible_component=inp.source_ledger_id,
                retry_schedule=retry_sched,
                blocking_dependency=inp.source_ledger_id if not inp.reachable_databases.get(inp.source_ledger_id, True) else None,
                operator_action_required=False,
                evidence_references=evidence,
            )
        if not inp.destination_confirmed:
            return RecoveryExplanation(
                transfer_id=inp.transfer_id,
                classification="COMMITTED_AWAITING_DEST_CONFIRM",
                current_state="COMMITTING",
                reason="The COMMIT decision is durable. Source confirmation succeeded. Destination confirmation has not been acknowledged.",
                safety_implication="The transfer cannot be cancelled or refunded; clearing is temporarily non-zero until destination settles.",
                next_action=f"Retry DESTINATION_CONFIRM on {inp.destination_ledger_id} via forward recovery worker.",
                responsible_component=inp.destination_ledger_id,
                retry_schedule=retry_sched,
                blocking_dependency=inp.destination_ledger_id if not inp.reachable_databases.get(inp.destination_ledger_id, True) else None,
                operator_action_required=False,
                evidence_references=evidence,
            )
        return RecoveryExplanation(
            transfer_id=inp.transfer_id,
            classification="COMMITTED_FINALIZING_COORDINATOR",
            current_state="COMMITTING",
            reason="Both source and destination confirmations succeeded; coordinator state transition to SETTLED is pending.",
            safety_implication="Participant ledgers are settled; coordinator only needs to mark transfer SETTLED.",
            next_action="Run recovery worker to finalize coordinator state to SETTLED.",
            responsible_component="coordinator",
            retry_schedule=retry_sched,
            operator_action_required=False,
            evidence_references=evidence,
        )

    # 5. CANCELLING state
    if inp.transfer_state == "CANCELLING":
        return RecoveryExplanation(
            transfer_id=inp.transfer_id,
            classification="CANCELLING_RELEASE_PENDING",
            current_state="CANCELLING",
            reason="Transfer is cancelling; participant cancel/tombstone and hold release are pending completion.",
            safety_implication="Transfer cannot commit or settle (invariant I9).",
            next_action="Retry participant CANCEL commands to release holds and write tombstones.",
            responsible_component="recovery_worker",
            retry_schedule=retry_sched,
            operator_action_required=False,
            evidence_references=evidence,
        )

    # 6. ACCEPTED / PREPARING states
    if inp.transfer_state in ("ACCEPTED", "PREPARING") and inp.decision is None:
        return RecoveryExplanation(
            transfer_id=inp.transfer_id,
            classification="PREPARING_IN_PROGRESS",
            current_state=inp.transfer_state,
            reason=f"Transfer is in {inp.transfer_state} phase with no durable decision yet.",
            safety_implication="May still commit if both prepares succeed, or cancel safely if a participant rejects.",
            next_action="Resume TCC orchestration from prepare phase.",
            responsible_component="coordinator",
            retry_schedule=retry_sched,
            operator_action_required=False,
            evidence_references=evidence,
        )

    # 7. Fallback: never invent an explanation
    return RecoveryExplanation(
        transfer_id=inp.transfer_id,
        classification="UNCLASSIFIED_STATE",
        current_state=inp.transfer_state,
        reason=f"Unclassified state combination: state={inp.transfer_state}, decision={inp.decision}.",
        safety_implication="Automated engine refuses to guess; manual inspection required.",
        next_action="Inspect coordinator and participant tables before taking action.",
        responsible_component="operator",
        retry_schedule="halted",
        operator_action_required=True,
        evidence_references=evidence,
    )


def _probe_db(url: str) -> bool:
    try:
        with psycopg.connect(url, connect_timeout=1) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
        return True
    except Exception:
        return False


def explain_transfer_from_db(
    coord_db_url: str,
    ledger_db_urls: dict[str, str],
    transfer_id: UUID,
) -> RecoveryExplanation:
    """Gather live state from Coordinator and Participant Ledgers and explain recovery."""
    reachability = {
        "coordinator": _probe_db(coord_db_url),
        "ledger-1": _probe_db(ledger_db_urls.get("ledger-1", settings.ledger1_db_url)),
        "ledger-2": _probe_db(ledger_db_urls.get("ledger-2", settings.ledger2_db_url)),
    }
    if not reachability["coordinator"]:
        return explain_transfer_recovery(
            RecoveryDiagnosticInput(
                transfer_id=str(transfer_id),
                transfer_state="UNKNOWN",
                reachable_databases=reachability,
            )
        )

    with get_db_connection(coord_db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT t.transfer_id, t.state, t.source_ledger_id, t.destination_ledger_id,
                       d.decision
                FROM transfers t
                LEFT JOIN transfer_decisions d ON t.transfer_id = d.transfer_id
                WHERE t.transfer_id = %s;
                """,
                (transfer_id,),
            )
            tx = cur.fetchone()
            if not tx:
                return RecoveryExplanation(
                    transfer_id=str(transfer_id),
                    classification="UNCLASSIFIED_STATE",
                    current_state="NOT_FOUND",
                    reason=f"Transfer {transfer_id} does not exist in coordinator database.",
                    safety_implication="No financial state found.",
                    next_action="Verify transfer_id.",
                    responsible_component="coordinator",
                    retry_schedule="none",
                    operator_action_required=True,
                )
            cur.execute(
                "SELECT event_type FROM workflow_events WHERE transfer_id = %s;",
                (transfer_id,),
            )
            events = {r["event_type"] for r in cur.fetchall()}

    src_lid = str(tx["source_ledger_id"])
    dst_lid = str(tx["destination_ledger_id"])
    src_hold_status = None
    src_intent = None
    dst_intent = None

    if reachability.get(src_lid, False) and src_lid in ledger_db_urls:
        with get_db_connection(ledger_db_urls[src_lid]) as sconn:
            with sconn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT status FROM holds WHERE transfer_id = %s LIMIT 1;", (transfer_id,))
                hr = cur.fetchone()
                if hr:
                    src_hold_status = str(hr["status"])
                cur.execute("SELECT status FROM transfer_intents WHERE transfer_id = %s LIMIT 1;", (transfer_id,))
                ir = cur.fetchone()
                if ir:
                    src_intent = str(ir["status"])

    if reachability.get(dst_lid, False) and dst_lid in ledger_db_urls:
        with get_db_connection(ledger_db_urls[dst_lid]) as dconn:
            with dconn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT status FROM transfer_intents WHERE transfer_id = %s LIMIT 1;", (transfer_id,))
                ir = cur.fetchone()
                if ir:
                    dst_intent = str(ir["status"])

    return explain_transfer_recovery(
        RecoveryDiagnosticInput(
            transfer_id=str(transfer_id),
            transfer_state=str(tx["state"]),
            decision=str(tx["decision"]) if tx["decision"] else None,
            source_ledger_id=src_lid,
            destination_ledger_id=dst_lid,
            source_intent_status=src_intent,
            destination_intent_status=dst_intent,
            source_hold_status=src_hold_status,
            source_confirmed="SOURCE_CONFIRMED" in events,
            destination_confirmed="DESTINATION_CONFIRMED" in events,
            reachable_databases=reachability,
        )
    )


def list_recovery_queue_with_explanations(
    coord_db_url: str,
    ledger_db_urls: dict[str, str],
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return all unresolved transfers paired with deterministic recovery explanations."""
    with get_db_connection(coord_db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT transfer_id, state, amount_minor, currency, created_at
                FROM transfers
                WHERE state NOT IN ('SETTLED', 'CANCELLED')
                ORDER BY created_at ASC
                LIMIT %s;
                """,
                (limit,),
            )
            rows = cur.fetchall()

    items: list[dict[str, Any]] = []
    for r in rows:
        exp = explain_transfer_from_db(coord_db_url, ledger_db_urls, UUID(str(r["transfer_id"])))
        items.append(
            {
                "transfer_id": str(r["transfer_id"]),
                "state": r["state"],
                "amount_minor": int(r["amount_minor"]),
                "currency": r["currency"],
                "created_at": r["created_at"].isoformat(),
                "explanation": exp.model_dump(),
            }
        )
    return items
