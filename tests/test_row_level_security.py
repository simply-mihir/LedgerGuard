"""Row-level security: a customer-scoped session sees only that customer's rows, fails closed,
cannot write, and the existing runtime/reporting roles are unchanged."""

from __future__ import annotations

import json
from uuid import UUID, uuid4

import psycopg
import pytest

from ledgerguard.config import settings
from ledgerguard.db.customer_scope import customer_scoped_transaction
from ledgerguard.domain.constants import SYSTEM_CASH_ACCOUNT_ID
from ledgerguard.domain.money import AmountPaise
from ledgerguard.participant.account_service import create_ledger_account
from ledgerguard.participant.posting_service import simulate_funding

APP_URL = settings.ledger1_db_url
ADMIN_URL = settings.ledger1_admin_db_url
REPORTER_URL = "postgresql://ledgerguard_reporter:ledgerguard_reporter_secret@localhost:5443/ledger1_db"
PROTECTED = ("ledger_accounts", "account_balances", "journal_headers", "journal_lines",
             "balance_snapshots")


class World:
    def __init__(self) -> None:
        self.c1, self.c2 = uuid4(), uuid4()
        self.a1 = create_ledger_account(APP_URL, customer_id=self.c1).account_id
        self.a2 = create_ledger_account(APP_URL, customer_id=self.c2).account_id
        simulate_funding(APP_URL, self.a1, AmountPaise(7_000))
        simulate_funding(APP_URL, self.a2, AmountPaise(3_000))
        # One journal that touches BOTH customers (c1 pays c2), plus its header id.
        self.shared_journal = uuid4()
        lines = [
            {"account_id": str(self.a1), "side": "DEBIT", "amount_minor": 500},
            {"account_id": str(self.a2), "side": "CREDIT", "amount_minor": 500},
        ]
        with psycopg.connect(APP_URL) as conn:
            conn.execute(
                "SELECT post_journal(%s, NULL, 'LOCAL_TRANSFER', 'INR', NULL, 'rls test', %s::jsonb)",
                (self.shared_journal, json.dumps(lines)),
            )
            conn.commit()


@pytest.fixture(scope="module")
def world() -> World:
    return World()


def _scoped(customer: UUID, sql: str, params: tuple[object, ...] = ()) -> list[tuple]:
    with psycopg.connect(ADMIN_URL) as conn:
        with customer_scoped_transaction(conn, customer):
            return conn.execute(sql, params).fetchall()


def test_scoped_session_sees_only_its_own_accounts_and_balances(world: World) -> None:
    accounts = _scoped(world.c1, "SELECT account_id, customer_id FROM ledger_accounts")
    assert accounts == [(world.a1, world.c1)]
    balances = _scoped(world.c1, "SELECT account_id, posted_balance_minor FROM account_balances")
    assert balances == [(world.a1, 6_500)]
    # And the other customer sees only theirs.
    assert _scoped(world.c2, "SELECT account_id FROM ledger_accounts") == [(world.a2,)]
    assert _scoped(world.c2, "SELECT posted_balance_minor FROM account_balances") == [(3_500,)]


def test_system_accounts_and_other_customers_are_invisible(world: World) -> None:
    rows = _scoped(world.c1, "SELECT 1 FROM ledger_accounts WHERE account_id = %s",
                   (SYSTEM_CASH_ACCOUNT_ID,))
    assert rows == []
    rows = _scoped(world.c1, "SELECT 1 FROM account_balances WHERE account_id = %s", (world.a2,))
    assert rows == []


def test_shared_journal_header_visible_but_counterparty_line_hidden(world: World) -> None:
    for me, mine, theirs in ((world.c1, world.a1, world.a2), (world.c2, world.a2, world.a1)):
        headers = _scoped(me, "SELECT journal_id FROM journal_headers WHERE journal_id = %s",
                          (world.shared_journal,))
        assert headers == [(world.shared_journal,)]
        lines = _scoped(me, "SELECT account_id FROM journal_lines WHERE journal_id = %s",
                        (world.shared_journal,))
        assert lines == [(mine,)]
        assert (theirs,) not in lines


def test_scoped_lines_never_include_other_accounts(world: World) -> None:
    lines = _scoped(world.c1, "SELECT DISTINCT account_id FROM journal_lines")
    assert lines == [(world.a1,)]
    # Funding journals for c2 (and the cash leg of c1's own funding) are not visible.
    with psycopg.connect(ADMIN_URL) as conn:  # unrestricted view: journals touching c1's account
        expected = conn.execute(
            "SELECT count(DISTINCT journal_id) FROM journal_lines WHERE account_id = %s",
            (world.a1,)).fetchone()
    assert expected is not None and expected[0] >= 2  # funding + the shared transfer
    assert _scoped(world.c1, "SELECT count(*) FROM journal_headers") == [(expected[0],)]


def test_unset_empty_or_unknown_scope_sees_nothing_and_malformed_scope_errors(world: World) -> None:
    with psycopg.connect(ADMIN_URL) as conn:
        with conn.transaction():
            conn.execute("SET LOCAL ROLE ledgerguard_customer_reader")
            for table in PROTECTED:  # never scoped: fails closed
                assert conn.execute(f"SELECT count(*) FROM {table}").fetchone() == (0,)
            conn.execute("SELECT set_config('ledgerguard.customer_id', '', true)")
            for table in PROTECTED:
                assert conn.execute(f"SELECT count(*) FROM {table}").fetchone() == (0,)
    assert _scoped(uuid4(), "SELECT count(*) FROM ledger_accounts") == [(0,)]
    with psycopg.connect(ADMIN_URL) as conn:
        with conn.transaction():
            conn.execute("SET LOCAL ROLE ledgerguard_customer_reader")
            conn.execute("SELECT set_config('ledgerguard.customer_id', 'not-a-uuid', true)")
            with pytest.raises(psycopg.errors.InvalidTextRepresentation):
                conn.execute("SELECT * FROM ledger_accounts")


def test_scope_and_role_do_not_leak_past_the_transaction(world: World) -> None:
    with psycopg.connect(ADMIN_URL) as conn:
        with customer_scoped_transaction(conn, world.c1):
            assert conn.execute("SELECT current_user").fetchone() == ("ledgerguard_customer_reader",)
        assert conn.execute("SELECT current_user").fetchone() == ("ledgerguard_admin",)
        assert conn.execute("SELECT ledgerguard_scope_customer()").fetchone() == (None,)


def test_customer_reader_is_read_only_and_confined_to_the_five_tables(world: World) -> None:
    with psycopg.connect(ADMIN_URL) as conn:
        for sql in (
            "INSERT INTO ledger_accounts (customer_id, account_type, normal_side) "
            "VALUES (gen_random_uuid(), 'LIABILITY', 'CREDIT')",
            "UPDATE account_balances SET posted_balance_minor = 0",
            "DELETE FROM journal_lines",
            "SELECT * FROM audit_events",
            "SELECT * FROM journal_chain_head",
            "SELECT * FROM participant_outbox",
        ):
            with conn.transaction():
                conn.execute("SET LOCAL ROLE ledgerguard_customer_reader")
                conn.execute("SELECT set_config('ledgerguard.customer_id', %s, true)",
                             (str(world.c1),))
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    with conn.transaction():
                        conn.execute(sql)


def test_customer_reader_cannot_log_in() -> None:
    with psycopg.connect(ADMIN_URL) as conn:
        row = conn.execute(
            "SELECT rolcanlogin, rolsuper, rolbypassrls FROM pg_roles "
            "WHERE rolname = 'ledgerguard_customer_reader'"
        ).fetchone()
    assert row == (False, False, False)


def test_runtime_and_reporting_roles_are_unchanged(world: World) -> None:
    with psycopg.connect(APP_URL) as conn:
        n = conn.execute("SELECT count(*) FROM ledger_accounts").fetchone()
        assert n is not None and n[0] >= 3  # both customers and the system accounts
        # The runtime role can still write through its policy (WITH CHECK true).
        conn.execute("SELECT post_journal(%s, NULL, 'FUNDING', 'INR', NULL, 'rls app', %s::jsonb)",
                     (uuid4(), json.dumps([
                         {"account_id": str(SYSTEM_CASH_ACCOUNT_ID), "side": "DEBIT",
                          "amount_minor": 1},
                         {"account_id": str(world.a1), "side": "CREDIT", "amount_minor": 1}])))
        conn.commit()
    with psycopg.connect(REPORTER_URL) as conn:
        for table in PROTECTED:
            row = conn.execute(f"SELECT count(*) FROM {table}").fetchone()
            assert row is not None and row[0] >= 1, table
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("UPDATE ledger_accounts SET name = 'x'")


def test_rls_is_enabled_but_not_forced_on_each_protected_table() -> None:
    with psycopg.connect(ADMIN_URL) as conn:
        rows = conn.execute(
            "SELECT relname, relrowsecurity, relforcerowsecurity FROM pg_class "
            "WHERE relname = ANY(%s) AND relkind = 'r'", (list(PROTECTED),)
        ).fetchall()
    assert {r[0] for r in rows} == set(PROTECTED)
    assert all(r[1] and not r[2] for r in rows)  # SECURITY DEFINER posting still bypasses RLS


def test_scope_is_a_session_setting_so_the_connector_must_be_trusted(world: World) -> None:
    """Documents the limit: the role can re-scope itself, so grant it only to trusted code."""
    with psycopg.connect(ADMIN_URL) as conn:
        with customer_scoped_transaction(conn, world.c1):
            conn.execute("SELECT set_config('ledgerguard.customer_id', %s, true)", (str(world.c2),))
            seen = conn.execute("SELECT account_id FROM ledger_accounts").fetchall()
    assert seen == [(world.a2,)]


def test_helper_rejects_non_uuid_scope() -> None:
    with psycopg.connect(ADMIN_URL) as conn:
        with pytest.raises(TypeError):
            with customer_scoped_transaction(conn, "x' OR '1'='1"):  # type: ignore[arg-type]
                pass

