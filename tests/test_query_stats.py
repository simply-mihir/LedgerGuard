"""pg_stat_statements is preloaded and attributes execution cost to normalised statements."""

from __future__ import annotations

import psycopg
import pytest

from ledgerguard.config import settings
from ledgerguard.db.query_stats import StatementStatsUnavailable, enable, top_statements

pytestmark = pytest.mark.integration

URLS = [settings.coordinator_admin_db_url, settings.ledger1_admin_db_url, settings.ledger2_admin_db_url]


@pytest.mark.parametrize("url", URLS)
def test_every_database_preloads_and_exposes_statement_statistics(url: str) -> None:
    try:
        enable(url)
    except StatementStatsUnavailable:
        pytest.fail("compose must preload pg_stat_statements on every database")
    marker = "SELECT 424242 AS query_stats_marker, pg_sleep(0.02)"
    with psycopg.connect(url) as c:
        for _ in range(3):
            c.execute(marker)
    mine = [s for s in top_statements(url, limit=500, order_by="calls") if "query_stats_marker" in s.query]
    assert mine and mine[0].calls >= 3 and mine[0].mean_ms >= 15


def test_ordering_is_allowlisted() -> None:
    with pytest.raises(ValueError):
        top_statements(URLS[0], order_by="calls; DROP TABLE transfers")
