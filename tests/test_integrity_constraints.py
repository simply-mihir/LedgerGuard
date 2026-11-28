"""Declarative integrity: the database itself refuses malformed currencies, bad refunds and bad amounts."""

from __future__ import annotations

from uuid import uuid4

import psycopg
import pytest

from ledgerguard.config import settings

pytestmark = pytest.mark.integration

EXPECTED = {
    settings.coordinator_admin_db_url: {
        "transfers_currency_format": True, "account_directory_currency_format": True,
        "transfers_refund_within_amount": True},
    settings.ledger1_admin_db_url: {
        "journal_headers_currency_format": True, "local_transfers_currency_format": True,
        "transfer_intents_currency_format": True, "transfer_reversals_amount_positive": True,
        "ledger_accounts_currency_format": None},  # NOT VALID: legacy dev rows tolerated, new rows enforced
    settings.ledger2_admin_db_url: {
        "journal_headers_currency_format": True, "local_transfers_currency_format": True,
        "transfer_intents_currency_format": True, "transfer_reversals_amount_positive": True,
        "ledger_accounts_currency_format": None},
}


@pytest.mark.parametrize("url", list(EXPECTED))
def test_constraints_exist_and_are_validated_where_data_allowed(url: str) -> None:
    with psycopg.connect(url) as c:
        got = dict(c.execute("SELECT conname, convalidated FROM pg_constraint WHERE contype = 'c'").fetchall())
    for name, validated in EXPECTED[url].items():
        assert name in got, name
        if validated is True:
            assert got[name] is True, f"{name} should be fully validated"


def test_the_database_refuses_a_lowercase_currency_on_a_new_account() -> None:
    with psycopg.connect(settings.ledger1_admin_db_url) as c:
        with pytest.raises(psycopg.errors.CheckViolation):
            c.execute("INSERT INTO ledger_accounts (account_id, account_type, normal_side, currency, status) "
                      "VALUES (%s, 'LIABILITY', 'CREDIT', 'inr', 'ACTIVE')", (uuid4(),))
        c.rollback()


def test_the_database_refuses_a_refund_total_above_the_transfer_amount() -> None:
    with psycopg.connect(settings.coordinator_admin_db_url) as c:
        tid, amount = c.execute(
            "SELECT transfer_id, amount_minor FROM transfers WHERE state = 'SETTLED' LIMIT 1").fetchone()  # type: ignore[misc]
        with pytest.raises(psycopg.errors.CheckViolation):
            c.execute("UPDATE transfers SET refunded_amount_minor = %s WHERE transfer_id = %s", (amount + 1, tid))
        c.rollback()
