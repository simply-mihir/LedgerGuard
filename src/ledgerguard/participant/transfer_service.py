from typing import Any, cast
from uuid import UUID, uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from ledgerguard.db.pool import get_db_connection
from ledgerguard.domain.idempotency import (
    IdempotencyConflictError,
    compute_payload_hash,
)
from ledgerguard.domain.models import (
    AccountType,
    JournalLineInput,
    JournalPostRequest,
    OperationType,
    PostingSide,
)
from ledgerguard.domain.money import AmountPaise
from ledgerguard.domain.templates import validate_journal_template


class TransferError(Exception):
    """Base exception for transfer execution failures."""

    pass


class InsufficientFundsError(TransferError):
    """Raised when source wallet has insufficient available balance."""

    pass


class AccountNotActiveError(TransferError):
    """Raised when source or destination wallet is not ACTIVE."""

    pass


class ReversalConflictError(TransferError):
    """Raised when attempting to reverse an already reversed transfer."""

    pass


class ReversalRejectedError(TransferError):
    """Raised when reversal conditions are not met (e.g. recipient spent funds)."""

    pass


def execute_local_transfer(
    db_url: str,
    idempotency_key: str,
    source_account_id: UUID,
    destination_account_id: UUID,
    amount: AmountPaise,
    correlation_id: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    """Execute an atomic local transfer between two wallets on the same ledger."""
    if source_account_id == destination_account_id:
        raise TransferError("Source and destination accounts must be distinct.")

    # Canonical payload dictionary for hash fingerprinting
    payload_dict = {
        "source": str(source_account_id),
        "destination": str(destination_account_id),
        "amount_minor": amount.paise,
        "currency": "INR",
        "operation": "LOCAL_TRANSFER",
    }
    payload_hash = compute_payload_hash(payload_dict)
    op_namespace = "local_transfer"

    with get_db_connection(db_url) as conn:
        cur: Any
        with conn.cursor(row_factory=dict_row) as cur:
            # 1. Check idempotency record
            cur.execute(
                """
                SELECT payload_hash, response_body
                FROM idempotency_records
                WHERE idempotency_key = %s AND operation_namespace = %s;
            """,
                (idempotency_key, op_namespace),
            )
            existing = cur.fetchone()
            if existing:
                if existing["payload_hash"] != payload_hash:
                    raise IdempotencyConflictError(
                        f"Idempotency key '{idempotency_key}' was previously used with a different payload."
                    )
                return cast(dict[str, Any], existing["response_body"])

            # 2. Acquire locks on both accounts in deterministic account_id ASC order
            sorted_acct_ids = sorted([source_account_id, destination_account_id])
            cur.execute(
                """
                SELECT
                    a.account_id, a.account_type, a.status,
                    b.posted_balance_minor, b.held_amount_minor
                FROM account_balances b
                JOIN ledger_accounts a ON b.account_id = a.account_id
                WHERE b.account_id = ANY(%s)
                ORDER BY b.account_id ASC;
            """,
                (sorted_acct_ids,),
            )
            rows = {r["account_id"]: r for r in cur.fetchall()}

            if len(rows) != 2:
                missing = [str(aid) for aid in sorted_acct_ids if aid not in rows]
                raise TransferError(f"Account(s) not found on ledger: {', '.join(missing)}")

            src_row = rows[source_account_id]
            dst_row = rows[destination_account_id]

            if src_row["status"] != "ACTIVE":
                raise AccountNotActiveError(
                    f"Source account {source_account_id} is {src_row['status']}."
                )
            if dst_row["status"] != "ACTIVE":
                raise AccountNotActiveError(
                    f"Destination account {destination_account_id} is {dst_row['status']}."
                )

            src_available = src_row["posted_balance_minor"] - src_row["held_amount_minor"]
            if src_available < amount.paise:
                raise InsufficientFundsError(
                    f"Insufficient available funds on source account: available {src_available}, required {amount.paise}."
                )

            # 3. Post double-entry journal via post_journal stored procedure
            transfer_id = uuid4()
            journal_id = uuid4()

            post_req = JournalPostRequest(
                journal_id=journal_id,
                transfer_id=transfer_id,
                operation_type=OperationType.LOCAL_TRANSFER,
                currency="INR",
                correlation_id=correlation_id,
                description=description
                or f"Local transfer {source_account_id} -> {destination_account_id}",
                lines=[
                    JournalLineInput(
                        account_id=source_account_id,
                        side=PostingSide.DEBIT,
                        amount=amount,
                    ),
                    JournalLineInput(
                        account_id=destination_account_id,
                        side=PostingSide.CREDIT,
                        amount=amount,
                    ),
                ],
            )
            # In-memory template validation
            validate_journal_template(
                post_req,
                {
                    source_account_id: AccountType(src_row["account_type"]),
                    destination_account_id: AccountType(dst_row["account_type"]),
                },
            )

            lines_payload = [
                {
                    "account_id": str(line.account_id),
                    "side": line.side.value,
                    "amount_minor": line.amount.paise,
                }
                for line in post_req.lines
            ]

            cur.execute(
                """
                SELECT post_journal(
                    %s, %s, %s, %s, %s, %s, %s
                ) AS result;
            """,
                (
                    journal_id,
                    transfer_id,
                    OperationType.LOCAL_TRANSFER.value,
                    "INR",
                    correlation_id,
                    post_req.description,
                    Jsonb(lines_payload),
                ),
            )

            # 4. Insert into local_transfers table
            cur.execute(
                """
                INSERT INTO local_transfers (
                    transfer_id, idempotency_key, payload_hash,
                    source_account_id, destination_account_id,
                    amount_minor, currency, journal_id, status
                ) VALUES (%s, %s, %s, %s, %s, %s, 'INR', %s, 'SETTLED');
            """,
                (
                    transfer_id,
                    idempotency_key,
                    payload_hash,
                    source_account_id,
                    destination_account_id,
                    amount.paise,
                    journal_id,
                ),
            )

            response_data = {
                "transfer_id": str(transfer_id),
                "status": "SETTLED",
                "source_account_id": str(source_account_id),
                "destination_account_id": str(destination_account_id),
                "amount_minor": amount.paise,
                "currency": "INR",
                "journal_id": str(journal_id),
            }

            # 5. Persist idempotency record in the same atomic transaction
            cur.execute(
                """
                INSERT INTO idempotency_records (
                    idempotency_key, operation_namespace, payload_hash,
                    status_code, response_body, resource_id
                ) VALUES (%s, %s, %s, 200, %s, %s);
            """,
                (
                    idempotency_key,
                    op_namespace,
                    payload_hash,
                    Jsonb(response_data),
                    str(transfer_id),
                ),
            )

        conn.commit()
        return response_data


def execute_reversal(
    db_url: str,
    idempotency_key: str,
    original_transfer_id: UUID,
    reason: str | None = None,
) -> dict[str, Any]:
    """Execute a single full reversal of a previously settled local transfer."""
    payload_dict = {
        "original_transfer_id": str(original_transfer_id),
        "operation": "REVERSAL",
    }
    payload_hash = compute_payload_hash(payload_dict)
    op_namespace = "reversal"

    with get_db_connection(db_url) as conn:
        cur: Any
        with conn.cursor(row_factory=dict_row) as cur:
            # 1. Check idempotency record
            cur.execute(
                """
                SELECT payload_hash, response_body
                FROM idempotency_records
                WHERE idempotency_key = %s AND operation_namespace = %s;
            """,
                (idempotency_key, op_namespace),
            )
            existing = cur.fetchone()
            if existing:
                if existing["payload_hash"] != payload_hash:
                    raise IdempotencyConflictError(
                        f"Idempotency key '{idempotency_key}' was previously used with a different reversal payload."
                    )
                return cast(dict[str, Any], existing["response_body"])

            # 2. Lock and load original transfer
            cur.execute(
                """
                SELECT
                    transfer_id, source_account_id, destination_account_id,
                    amount_minor, currency, status
                FROM local_transfers
                WHERE transfer_id = %s
                FOR UPDATE;
            """,
                (original_transfer_id,),
            )
            orig = cur.fetchone()
            if not orig:
                raise TransferError(f"Original transfer {original_transfer_id} not found.")

            if orig["status"] == "REVERSED":
                raise ReversalConflictError(
                    f"Transfer {original_transfer_id} has already been reversed."
                )

            # Check transfer_reversals table for duplicate prevention
            cur.execute(
                """
                SELECT reversal_id FROM transfer_reversals
                WHERE original_transfer_id = %s;
            """,
                (original_transfer_id,),
            )
            if cur.fetchone():
                raise ReversalConflictError(
                    f"Transfer {original_transfer_id} has already been reversed."
                )

            orig_source_id = orig["source_account_id"]
            orig_dest_id = orig["destination_account_id"]
            reversal_amount = orig["amount_minor"]

            # Reversal direction: Debit orig_dest (recipient), Credit orig_source (sender)
            sorted_acct_ids = sorted([orig_source_id, orig_dest_id])
            cur.execute(
                """
                SELECT
                    a.account_id, a.account_type, a.status,
                    b.posted_balance_minor, b.held_amount_minor
                FROM account_balances b
                JOIN ledger_accounts a ON b.account_id = a.account_id
                WHERE b.account_id = ANY(%s)
                ORDER BY b.account_id ASC;
            """,
                (sorted_acct_ids,),
            )
            rows = {r["account_id"]: r for r in cur.fetchall()}

            dest_row = rows[orig_dest_id]
            dest_available = dest_row["posted_balance_minor"] - dest_row["held_amount_minor"]

            if dest_available < reversal_amount:
                raise ReversalRejectedError(
                    f"Recipient account {orig_dest_id} has insufficient funds for reversal: "
                    f"available {dest_available}, needed {reversal_amount}."
                )

            # 3. Post reversal journal
            reversal_transfer_id = uuid4()
            reversal_journal_id = uuid4()

            lines_payload = [
                {
                    "account_id": str(orig_dest_id),
                    "side": PostingSide.DEBIT.value,
                    "amount_minor": reversal_amount,
                },
                {
                    "account_id": str(orig_source_id),
                    "side": PostingSide.CREDIT.value,
                    "amount_minor": reversal_amount,
                },
            ]

            cur.execute(
                """
                SELECT post_journal(
                    %s, %s, %s, %s, %s, %s, %s
                ) AS result;
            """,
                (
                    reversal_journal_id,
                    reversal_transfer_id,
                    OperationType.REVERSAL.value,
                    "INR",
                    str(original_transfer_id),
                    f"Full reversal of transfer {original_transfer_id}: {reason or 'No reason provided'}",
                    Jsonb(lines_payload),
                ),
            )

            # 4. Insert reversal transfer
            cur.execute(
                """
                INSERT INTO local_transfers (
                    transfer_id, idempotency_key, payload_hash,
                    source_account_id, destination_account_id,
                    amount_minor, currency, journal_id, status
                ) VALUES (%s, %s, %s, %s, %s, %s, 'INR', %s, 'SETTLED');
            """,
                (
                    reversal_transfer_id,
                    idempotency_key,
                    payload_hash,
                    orig_dest_id,
                    orig_source_id,
                    reversal_amount,
                    reversal_journal_id,
                ),
            )

            # 5. Insert unique link into transfer_reversals table
            reversal_record_id = uuid4()
            cur.execute(
                """
                INSERT INTO transfer_reversals (
                    reversal_id, original_transfer_id, reversal_transfer_id,
                    amount_minor, reason
                ) VALUES (%s, %s, %s, %s, %s);
            """,
                (
                    reversal_record_id,
                    original_transfer_id,
                    reversal_transfer_id,
                    reversal_amount,
                    reason,
                ),
            )

            # 6. Update original transfer status to REVERSED
            cur.execute(
                """
                UPDATE local_transfers
                SET status = 'REVERSED'
                WHERE transfer_id = %s;
            """,
                (original_transfer_id,),
            )

            response_data = {
                "reversal_id": str(reversal_record_id),
                "original_transfer_id": str(original_transfer_id),
                "reversal_transfer_id": str(reversal_transfer_id),
                "status": "REVERSED",
                "amount_minor": reversal_amount,
                "currency": "INR",
            }

            # 7. Persist idempotency record
            cur.execute(
                """
                INSERT INTO idempotency_records (
                    idempotency_key, operation_namespace, payload_hash,
                    status_code, response_body, resource_id
                ) VALUES (%s, %s, %s, 200, %s, %s);
            """,
                (
                    idempotency_key,
                    op_namespace,
                    payload_hash,
                    Jsonb(response_data),
                    str(reversal_record_id),
                ),
            )

        conn.commit()
        return response_data


def get_transfer_details(db_url: str, transfer_id: UUID) -> dict[str, Any]:
    """Retrieve full transfer details and reversal link if any."""
    with get_db_connection(db_url) as conn:
        cur: Any
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    t.transfer_id, t.idempotency_key, t.source_account_id,
                    t.destination_account_id, t.amount_minor, t.currency,
                    t.journal_id, t.status, t.created_at,
                    r.reversal_id, r.reversal_transfer_id, r.created_at AS reversed_at
                FROM local_transfers t
                LEFT JOIN transfer_reversals r ON t.transfer_id = r.original_transfer_id
                WHERE t.transfer_id = %s;
            """,
                (transfer_id,),
            )
            row = cur.fetchone()
            if not row:
                raise TransferError(f"Transfer {transfer_id} not found.")

            return {
                "transfer_id": str(row["transfer_id"]),
                "idempotency_key": row["idempotency_key"],
                "source_account_id": str(row["source_account_id"]),
                "destination_account_id": str(row["destination_account_id"]),
                "amount_minor": row["amount_minor"],
                "currency": row["currency"],
                "journal_id": str(row["journal_id"]),
                "status": row["status"],
                "created_at": row["created_at"].isoformat(),
                "is_reversed": row["reversal_id"] is not None,
                "reversal_id": str(row["reversal_id"]) if row["reversal_id"] else None,
                "reversal_transfer_id": str(row["reversal_transfer_id"])
                if row["reversal_transfer_id"]
                else None,
            }
