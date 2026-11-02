"""Account lifecycle and authoritative balance services."""

from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row

from ledgerguard.db.pool import get_db_connection
from ledgerguard.domain.models import (
    AccountBalanceView,
    AccountStatus,
    AccountType,
    NormalSide,
    PostingSide,
    StatementEntry,
)


class AccountNotFoundError(Exception):
    """Raised when an account is not found in the ledger."""

    pass


class AccountLifecycleError(Exception):
    """Raised when an account status transition violates business invariants."""

    pass


def create_ledger_account(
    db_url: str,
    account_id: UUID | None = None,
    customer_id: UUID | None = None,
    account_type: AccountType = AccountType.LIABILITY,
    normal_side: NormalSide | None = None,
    currency: str = "INR",
    name: str | None = None,
) -> AccountBalanceView:
    """Create a new ledger account and its associated zeroed balance row."""
    acct_id = account_id or uuid4()
    if normal_side is None:
        normal_side = (
            NormalSide.CREDIT if account_type == AccountType.LIABILITY else NormalSide.DEBIT
        )

    with get_db_connection(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO ledger_accounts (
                    account_id, customer_id, account_type, normal_side, currency, status, name
                ) VALUES (%s, %s, %s, %s, %s, 'ACTIVE', %s);
            """,
                (acct_id, customer_id, account_type.value, normal_side.value, currency, name),
            )

            cur.execute(
                """
                INSERT INTO account_balances (
                    account_id, posted_balance_minor, held_amount_minor, account_sequence, version
                ) VALUES (%s, 0, 0, 0, 0);
            """,
                (acct_id,),
            )
        conn.commit()

    return get_account_balance(db_url, acct_id)


def get_account_balance(db_url: str, account_id: UUID) -> AccountBalanceView:
    """Return authoritative balance, held amount, and version for an account."""
    with get_db_connection(db_url) as conn:
        cur: Any
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT
                    a.account_id,
                    a.currency,
                    a.status,
                    b.posted_balance_minor,
                    b.held_amount_minor,
                    b.account_sequence,
                    b.version
                FROM ledger_accounts a
                JOIN account_balances b ON a.account_id = b.account_id
                WHERE a.account_id = %s;
            """,
                (account_id,),
            )
            row = cur.fetchone()
            if not row:
                raise AccountNotFoundError(f"Account {account_id} not found.")

            posted = row["posted_balance_minor"]
            held = row["held_amount_minor"]
            available = posted - held

            return AccountBalanceView(
                account_id=row["account_id"],
                currency=row["currency"],
                posted_balance_minor=posted,
                held_amount_minor=held,
                available_balance_minor=available,
                account_sequence=row["account_sequence"],
                version=row["version"],
                status=AccountStatus(row["status"]),
            )


def get_statement(
    db_url: str,
    account_id: UUID,
    cursor_sequence: int | None = None,
    limit: int = 50,
) -> tuple[list[StatementEntry], int | None]:
    """Retrieve chronological statement entries for an account using account sequence cursor pagination."""
    _ = get_account_balance(db_url, account_id)

    query = """
        SELECT
            l.journal_id,
            l.line_no,
            l.account_sequence,
            h.operation_type,
            l.side,
            l.amount_minor,
            h.currency,
            h.created_at,
            h.description,
            h.correlation_id,
            h.transfer_id
        FROM journal_lines l
        JOIN journal_headers h ON l.journal_id = h.journal_id
        WHERE l.account_id = %s
    """
    params: list[Any] = [account_id]
    if cursor_sequence is not None:
        query += " AND l.account_sequence > %s"
        params.append(cursor_sequence)

    query += " ORDER BY l.account_sequence ASC LIMIT %s;"
    params.append(limit + 1)

    with get_db_connection(db_url) as conn:
        cur: Any
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()

    has_more = len(rows) > limit
    results_to_return = rows[:limit]

    entries = [
        StatementEntry(
            journal_id=r["journal_id"],
            line_no=r["line_no"],
            account_sequence=r["account_sequence"],
            operation_type=r["operation_type"],
            side=PostingSide(r["side"]),
            amount_minor=r["amount_minor"],
            currency=r["currency"],
            created_at=r["created_at"],
            description=r["description"],
            correlation_id=r["correlation_id"],
            transfer_id=r["transfer_id"],
        )
        for r in results_to_return
    ]

    next_cursor = results_to_return[-1]["account_sequence"] if has_more else None
    return entries, next_cursor


def set_account_status(
    db_url: str,
    account_id: UUID,
    new_status: AccountStatus,
    reason: str | None = None,
) -> AccountBalanceView:
    """Transition an account status (ACTIVE, FROZEN, CLOSED) under lock."""
    with get_db_connection(db_url) as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT update_account_status(%s, %s, %s);",
                    (account_id, new_status.value, reason),
                )
            conn.commit()
        except psycopg.Error as exc:
            conn.rollback()
            msg = str(exc)
            if "not found" in msg:
                raise AccountNotFoundError(f"Account {account_id} not found.") from exc
            raise AccountLifecycleError(msg) from exc

    return get_account_balance(db_url, account_id)
