"""Print the most expensive statements per database. Run: uv run python scripts/top_statements.py [limit]"""

import sys

from ledgerguard.config import settings
from ledgerguard.db.query_stats import StatementStatsUnavailable, top_statements

limit = int(sys.argv[1]) if len(sys.argv) > 1 else 5
for name, url in (("coordinator", settings.coordinator_admin_db_url), ("ledger-1", settings.ledger1_admin_db_url),
                  ("ledger-2", settings.ledger2_admin_db_url)):
    print(f"== {name}")
    try:
        for s in top_statements(url, limit):
            print(f"{s.total_ms:10.1f} ms total  {s.calls:7d} calls  {s.mean_ms:7.2f} ms avg  {s.query[:90]!r}")
    except StatementStatsUnavailable as exc:
        print(f"  unavailable: {exc}")
