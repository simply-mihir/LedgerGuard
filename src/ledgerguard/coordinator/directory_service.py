"""Account directory service managing customer registration, ledger routing, and idempotent provisioning."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from psycopg.rows import dict_row

from ledgerguard.db.pool import get_db_connection
from ledgerguard.participant.account_service import create_ledger_account


class DirectoryError(Exception):
    """Base exception for directory operations."""


class AccountRoutingNotFoundError(DirectoryError):
    """Raised when an account is not registered in the routing directory."""


class ProvisioningError(DirectoryError):
    """Raised when account provisioning fails."""


def register_customer(
    coord_db_url: str,
    name: str,
    email: str,
    customer_id: UUID | None = None,
) -> dict[str, Any]:
    """Register a customer in the coordinator database."""
    cust_id = customer_id or uuid4()
    with get_db_connection(coord_db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO customers (customer_id, name, email, status)
                VALUES (%s, %s, %s, 'ACTIVE')
                ON CONFLICT (email) DO UPDATE
                SET name = EXCLUDED.name
                RETURNING customer_id, name, email, status, created_at;
            """,
                (cust_id, name, email),
            )
            row = cur.fetchone()
            if not row:
                raise DirectoryError("Failed to register customer.")
        conn.commit()

    return dict(row)


def provision_account(
    coord_db_url: str,
    ledger_db_urls: dict[str, str],
    customer_id: UUID,
    ledger_id: str,
    currency: str = "INR",
    account_id: UUID | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    """Idempotently provision a new customer wallet on a target participant ledger.

    Lifecycle:
    1. Register routing directory entry in PROVISIONING state.
    2. Provision ledger_accounts and account_balances on participant database.
    3. Transition routing directory entry to READY state with incremented version.
    """
    if ledger_id not in ledger_db_urls:
        raise ProvisioningError(f"Target ledger '{ledger_id}' not configured in ledger_db_urls.")

    target_acct_id = account_id or uuid4()

    with get_db_connection(coord_db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            # Check if directory entry already exists
            cur.execute(
                """
                SELECT account_id, customer_id, ledger_id, provisioning_state, routing_version, currency
                FROM account_directory
                WHERE account_id = %s;
            """,
                (target_acct_id,),
            )
            existing = cur.fetchone()

            if existing:
                if existing["provisioning_state"] == "READY":
                    return dict(existing)
                # If still PROVISIONING, resume
            else:
                cur.execute(
                    """
                    INSERT INTO account_directory (
                        account_id, customer_id, ledger_id, provisioning_state, routing_version, currency
                    ) VALUES (%s, %s, %s, 'PROVISIONING', 1, %s);
                """,
                    (target_acct_id, customer_id, ledger_id, currency),
                )
        conn.commit()

    # Provision account on participant ledger
    participant_db_url = ledger_db_urls[ledger_id]
    create_ledger_account(
        participant_db_url,
        customer_id=customer_id,
        currency=currency,
        name=name,
        account_id=target_acct_id,
    )

    # Mark READY in directory
    with get_db_connection(coord_db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                UPDATE account_directory
                SET provisioning_state = 'READY',
                    routing_version = routing_version + 1,
                    updated_at = NOW()
                WHERE account_id = %s
                RETURNING account_id, customer_id, ledger_id, provisioning_state, routing_version, currency;
            """,
                (target_acct_id,),
            )
            updated = cur.fetchone()
            if not updated:
                raise ProvisioningError(f"Failed to update directory status for {target_acct_id}.")
        conn.commit()

    return dict(updated)


def get_account_routing(coord_db_url: str, account_id: UUID) -> dict[str, Any]:
    """Look up authoritative routing metadata for an account."""
    with get_db_connection(coord_db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT account_id, customer_id, ledger_id, provisioning_state, routing_version, currency
                FROM account_directory
                WHERE account_id = %s;
            """,
                (account_id,),
            )
            row = cur.fetchone()
            if not row:
                raise AccountRoutingNotFoundError(f"Account {account_id} not found in directory.")

            if row["provisioning_state"] != "READY":
                raise ProvisioningError(
                    f"Account {account_id} is in state '{row['provisioning_state']}', not READY."
                )

    return dict(row)
