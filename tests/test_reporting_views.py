"""Reporting views: one database-side definition of balances and trial balance, readable by the reporter."""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest

from ledgerguard.config import settings

pytestmark = pytest.mark.integration

REPORTER_PASSWORD = "ledgerguard_reporter_secret"  # the dev role password used by test_auth_permissions


def _as_reporter(url: str) -> str:
    p = urlsplit(url)
    return urlunsplit((p.scheme, f"ledgerguard_reporter:{REPORTER_PASSWORD}@{p.hostname}:{p.port}", p.path, "", ""))


LEDGERS = [settings.ledger1_admin_db_url, settings.ledger2_admin_db_url]


@pytest.mark.parametrize("admin_url", LEDGERS)
def test_trial_balance_view_balances_and_agrees_with_raw_lines(admin_url: str) -> None:
    with psycopg.connect(_as_reporter(admin_url)) as c:
        rows = c.execute("SELECT currency, total_debit_minor, total_credit_minor, imbalance_minor FROM v_trial_balance").fetchall()
        raw = c.execute(
            "SELECT COALESCE(SUM(amount_minor) FILTER (WHERE side='DEBIT'),0), "
            "COALESCE(SUM(amount_minor) FILTER (WHERE side='CREDIT'),0) FROM journal_lines").fetchone()
    assert rows, "ledger has postings, so the view must have rows"
    assert all(r[3] == 0 and r[1] == r[2] for r in rows)
    assert (sum(r[1] for r in rows), sum(r[2] for r in rows)) == tuple(raw)  # type: ignore[arg-type]


@pytest.mark.parametrize("admin_url", LEDGERS)
def test_account_balances_view_matches_the_ledger_balance_function(admin_url: str) -> None:
    with psycopg.connect(admin_url) as admin:
        sample = admin.execute(
            "SELECT account_id, posted_balance_minor FROM account_balances ORDER BY random() LIMIT 25").fetchall()
    assert sample
    with psycopg.connect(_as_reporter(admin_url)) as c:
        for account_id, posted in sample:
            got = c.execute("SELECT balance_minor FROM v_account_balances WHERE account_id = %s", (account_id,)).fetchone()
            assert got is not None and got[0] == posted, account_id


def test_views_are_read_only_for_the_reporter_and_use_the_callers_privileges() -> None:
    with psycopg.connect(settings.ledger1_admin_db_url) as admin:
        for view in ("v_trial_balance", "v_account_balances"):
            privs = {p: admin.execute("SELECT has_table_privilege('ledgerguard_reporter', %s, %s)",
                                      (view, p)).fetchone()[0]  # type: ignore[index]
                     for p in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE")}
            assert privs == {"SELECT": True, "INSERT": False, "UPDATE": False, "DELETE": False, "TRUNCATE": False}
    with psycopg.connect(settings.ledger1_admin_db_url) as admin:
        opts = admin.execute(
            "SELECT relname, reloptions FROM pg_class WHERE relname IN ('v_trial_balance','v_account_balances')").fetchall()
    assert len(opts) == 2 and all("security_invoker=true" in (o[1] or []) for o in opts)


def test_coordinator_views_summarise_and_list_open_transfers() -> None:
    with psycopg.connect(_as_reporter(settings.coordinator_admin_db_url)) as c:
        summary = c.execute("SELECT state, transfers FROM v_transfer_state_summary").fetchall()
        total = c.execute("SELECT count(*) FROM transfers").fetchone()[0]  # type: ignore[index]
        open_ = c.execute("SELECT state, age_seconds FROM v_open_transfers").fetchall()
    assert sum(s[1] for s in summary) == total
    assert all(o[0] in {"ACCEPTED", "PREPARING", "COMMITTING", "CANCELLING"} and o[1] >= 0 for o in open_)
