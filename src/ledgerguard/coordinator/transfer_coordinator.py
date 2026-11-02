"""Distributed transfer coordinator handling idempotency, directory lookup, and 2PC initiation."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from ledgerguard.coordinator.directory_service import get_account_routing
from ledgerguard.coordinator.failpoints import FailpointManager
from ledgerguard.coordinator.failpoints import failpoints as default_failpoints
from ledgerguard.db.pool import get_db_connection
from ledgerguard.domain.idempotency import IdempotencyConflictError, compute_payload_hash
from ledgerguard.domain.money import AmountPaise
from ledgerguard.worker.orchestrator import execute_two_phase_commit


def submit_coordinator_transfer(
    coord_db_url: str,
    ledger_db_urls: dict[str, str],
    idempotency_key: str,
    source_account_id: UUID,
    destination_account_id: UUID,
    amount: AmountPaise,
    currency: str = "INR",
    transfer_id: UUID | None = None,
    failpoint_mgr: FailpointManager | None = None,
) -> dict[str, Any]:
    """Submit a transfer to the coordinator with idempotency and distributed 2PC orchestration."""
    payload_dict = {
        "source_account_id": str(source_account_id),
        "destination_account_id": str(destination_account_id),
        "amount_minor": amount.paise,
        "currency": currency,
    }
    payload_hash = compute_payload_hash(payload_dict)
    t_id = transfer_id or uuid4()

    # 1. Check idempotency record
    with get_db_connection(coord_db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT idempotency_key, payload_hash, status_code, response_body, resource_id
                FROM api_idempotency
                WHERE idempotency_key = %s AND operation_namespace = 'TRANSFERS';
            """,
                (idempotency_key,),
            )
            existing_rec = cur.fetchone()

            if existing_rec:
                if existing_rec["payload_hash"] != payload_hash:
                    raise IdempotencyConflictError(
                        f"Idempotency conflict: key '{idempotency_key}' reused with different payload."
                    )
                return dict(existing_rec["response_body"])

    # 2. Look up account directory routing
    source_routing = get_account_routing(coord_db_url, source_account_id)
    dest_routing = get_account_routing(coord_db_url, destination_account_id)

    transfer_type = (
        "LOCAL"
        if source_routing["ledger_id"] == dest_routing["ledger_id"]
        else "CROSS_LEDGER"
    )

    # 3. Insert transfer in ACCEPTED state
    with get_db_connection(coord_db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO transfers (
                    transfer_id, idempotency_key, source_account_id, destination_account_id,
                    amount_minor, currency, transfer_type, state,
                    source_ledger_id, destination_ledger_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'ACCEPTED', %s, %s)
                ON CONFLICT (transfer_id) DO NOTHING;
            """,
                (
                    t_id,
                    idempotency_key,
                    source_account_id,
                    destination_account_id,
                    amount.paise,
                    currency,
                    transfer_type,
                    source_routing["ledger_id"],
                    dest_routing["ledger_id"],
                ),
            )
        conn.commit()

    # 4. Execute 2PC orchestration
    result = execute_two_phase_commit(
        coord_db_url,
        t_id,
        ledger_db_urls,
        failpoint_mgr=failpoint_mgr or default_failpoints,
    )

    response_payload = {
        "transfer_id": str(t_id),
        "status": result["status"],
        "source_account_id": str(source_account_id),
        "destination_account_id": str(destination_account_id),
        "amount_minor": amount.paise,
        "currency": currency,
        "transfer_type": transfer_type,
        "reason": result.get("reason"),
    }

    # 5. Persist idempotency receipt
    with get_db_connection(coord_db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO api_idempotency (
                    idempotency_key, operation_namespace, payload_hash,
                    status_code, response_body, resource_id
                ) VALUES (%s, 'TRANSFERS', %s, 200, %s, %s)
                ON CONFLICT (idempotency_key, operation_namespace) DO NOTHING;
            """,
                (idempotency_key, payload_hash, Jsonb(response_payload), str(t_id)),
            )
        conn.commit()

    return response_payload
