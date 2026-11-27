"""Disk-full fault: a full data volume must fail writes cleanly and lose or corrupt nothing."""

from __future__ import annotations

from uuid import uuid4

import psycopg
import pytest

from ledgerguard.audit.journal_chain import verify_journal_chain
from ledgerguard.db.errors import is_infrastructure_error
from ledgerguard.db.pool import close_all_pools
from ledgerguard.domain.money import AmountPaise
from ledgerguard.faults.disk_full import SmallDiskPostgres, docker_available
from ledgerguard.participant.account_service import create_ledger_account
from ledgerguard.participant.posting_service import PostingError, simulate_funding
from ledgerguard.participant.reconciliation_service import run_local_reconciliation

pytestmark = pytest.mark.skipif(not docker_available(), reason="docker or postgres:17-alpine not available")


def _app(pg: SmallDiskPostgres) -> str:
    return pg.url("ledgerguard_app", "ledgerguard_app_secret")


def _count_journals(pg: SmallDiskPostgres) -> int:
    with psycopg.connect(pg.url()) as c:
        return int(c.execute("SELECT count(*) FROM journal_headers").fetchone()[0])  # type: ignore[index]


@pytest.fixture(autouse=True)
def _close_pools():
    yield
    close_all_pools()


def test_full_data_volume_fails_postings_cleanly_and_recovers() -> None:
    with SmallDiskPostgres() as pg:
        app = _app(pg)
        acct = create_ledger_account(app, account_id=uuid4()).account_id
        for _ in range(5):
            simulate_funding(app, acct, AmountPaise(1000))
        before = _count_journals(pg)

        assert pg.fill_tablespace() > 0

        # Postings now fail. Each failure is an infrastructure error (SQLSTATE 53100), not a PostingError.
        # Existing pages still have room, so keep posting until the volume actually refuses to grow.
        failures: list[BaseException] = []
        for _ in range(20_000):
            if len(failures) >= 10:
                break
            try:
                simulate_funding(app, acct, AmountPaise(1000))
            except PostingError:
                pytest.fail("a full disk was reported as a client-side PostingError")
            except Exception as exc:  # noqa: BLE001
                failures.append(exc)
        assert failures, "expected the filled tablespace to reject writes"
        assert all(isinstance(f, psycopg.errors.DiskFull) for f in failures), failures
        assert all(is_infrastructure_error(f) for f in failures)

        # Reads still work, and what was committed is intact: balanced, chained, reconciled.
        committed = _count_journals(pg)
        assert committed >= before
        report = run_local_reconciliation(pg.url())
        assert report.status == "PASS", report
        chain = verify_journal_chain(pg.url(), "ledger-1")
        assert chain.status == "PASS", chain
        with psycopg.connect(pg.url()) as c:
            bal = c.execute("SELECT posted_balance_minor FROM account_balances WHERE account_id = %s",
                            (acct,)).fetchone()[0]  # type: ignore[index]
        assert bal == 1000 * committed  # every committed journal credited exactly 1000; none half-applied

        # Space returns; the same ledger accepts new postings and the chain continues unbroken.
        pg.free_space()
        simulate_funding(app, acct, AmountPaise(1000))
        assert _count_journals(pg) == committed + 1
        assert verify_journal_chain(pg.url(), "ledger-1").status == "PASS"
        assert run_local_reconciliation(pg.url()).status == "PASS"
