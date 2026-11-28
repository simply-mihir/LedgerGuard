"""Double-entry journal posting service calling database stored procedure."""

import json
from typing import Any
from uuid import UUID, uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from ledgerguard.db.errors import is_infrastructure_error
from ledgerguard.db.pool import get_db_connection
from ledgerguard.domain.constants import SYSTEM_CASH_ACCOUNT_ID
from ledgerguard.domain.idempotency import IdempotencyConflictError
from ledgerguard.domain.models import (
    AccountType,
    JournalLineInput,
    JournalPostRequest,
    OperationType,
    PostingSide,
)
from ledgerguard.domain.money import AmountPaise
from ledgerguard.domain.templates import validate_journal_template
from ledgerguard.participant import request_idempotency


class PostingError(Exception):
    """Raised when a journal posting fails at the database or template layer."""

    pass


def post_journal_entry(
    db_url: str,
    request: JournalPostRequest,
    idempotency: tuple[str, str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Validate template rules and post a double-entry journal atomically to PostgreSQL.

    ``idempotency`` is ``(scope, key, payload)``. The claim is taken in the same transaction as the
    posting, so a retried or concurrent duplicate returns the first request's result and posts nothing.
    """
    # 1. Fetch account types to perform business template validation
    account_ids = [line.account_id for line in request.lines]
    account_types: dict[UUID, AccountType] = {}

    with get_db_connection(db_url) as conn:
        cur: Any
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT account_id, account_type
                FROM ledger_accounts
                WHERE account_id = ANY(%s);
            """,
                (account_ids,),
            )
            rows = cur.fetchall()
            for r in rows:
                account_types[r["account_id"]] = AccountType(r["account_type"])

    # 2. In-application business template validation
    validate_journal_template(request, account_types)

    # 3. Format lines for post_journal SQL function
    lines_payload = [
        {
            "account_id": str(line.account_id),
            "side": line.side.value,
            "amount_minor": line.amount.paise,
        }
        for line in request.lines
    ]

    # 4. Call database stored procedure under transaction
    with get_db_connection(db_url) as conn:
        try:
            if idempotency is not None:
                scope, key, payload = idempotency
                replay = request_idempotency.claim(conn, scope, key, payload)
                if replay is not None:
                    conn.rollback()  # nothing was written; release the connection cleanly
                    return {**replay, "idempotent_replay": True}
            cur2: Any
            with conn.cursor(row_factory=dict_row) as cur2:
                cur2.execute(
                    """
                    SELECT post_journal(
                        %s, %s, %s, %s, %s, %s, %s
                    ) AS result;
                """,
                    (
                        request.journal_id,
                        request.transfer_id,
                        request.operation_type.value,
                        request.currency,
                        request.correlation_id,
                        request.description,
                        Jsonb(lines_payload),
                    ),
                )
                row = cur2.fetchone()
                result = row["result"] if row else {}
            result = result if isinstance(result, dict) else json.loads(result)
            if idempotency is not None:
                request_idempotency.complete(conn, idempotency[0], idempotency[1], result)
            conn.commit()
            return result
        except IdempotencyConflictError:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            if is_infrastructure_error(exc):
                raise  # disk full, shutdown, lock timeout...: not a statement about the request
            raise PostingError(f"Posting failed: {exc}") from exc


def simulate_funding(
    db_url: str,
    account_id: UUID,
    amount: AmountPaise,
    correlation_id: str | None = None,
    description: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Deposit funds into a customer wallet from the platform cash asset account."""
    request = JournalPostRequest(
        journal_id=uuid4(),
        operation_type=OperationType.FUNDING,
        currency="INR",
        correlation_id=correlation_id,
        description=description or "Simulated customer account funding",
        lines=[
            JournalLineInput(
                account_id=SYSTEM_CASH_ACCOUNT_ID,
                side=PostingSide.DEBIT,
                amount=amount,
            ),
            JournalLineInput(
                account_id=account_id,
                side=PostingSide.CREDIT,
                amount=amount,
            ),
        ],
    )
    idem = (
        (request_idempotency.FUNDING, idempotency_key,
         {"account_id": str(account_id), "amount_minor": int(amount), "currency": "INR"})
        if idempotency_key else None
    )
    return post_journal_entry(db_url, request, idem)


def simulate_cash_out(
    db_url: str,
    account_id: UUID,
    amount: AmountPaise,
    correlation_id: str | None = None,
    description: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Withdraw funds from a customer wallet into the platform cash asset account."""
    request = JournalPostRequest(
        journal_id=uuid4(),
        operation_type=OperationType.CASH_OUT,
        currency="INR",
        correlation_id=correlation_id,
        description=description or "Simulated customer cash-out",
        lines=[
            JournalLineInput(
                account_id=account_id,
                side=PostingSide.DEBIT,
                amount=amount,
            ),
            JournalLineInput(
                account_id=SYSTEM_CASH_ACCOUNT_ID,
                side=PostingSide.CREDIT,
                amount=amount,
            ),
        ],
    )
    idem = (
        (request_idempotency.CASH_OUT, idempotency_key,
         {"account_id": str(account_id), "amount_minor": int(amount), "currency": "INR"})
        if idempotency_key else None
    )
    return post_journal_entry(db_url, request, idem)
