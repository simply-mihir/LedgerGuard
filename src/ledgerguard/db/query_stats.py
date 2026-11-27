"""Per-statement execution statistics from ``pg_stat_statements``.

The extension must be preloaded (``shared_preload_libraries``, set in docker-compose); creating it is a
per-database, admin-only step done here rather than in a migration so that a PostgreSQL without the
preload cannot break schema migration.
"""

from __future__ import annotations

from dataclasses import dataclass

import psycopg


class StatementStatsUnavailable(RuntimeError):
    """pg_stat_statements is not preloaded on this server."""


@dataclass(frozen=True)
class StatementStat:
    query: str
    calls: int
    total_ms: float
    mean_ms: float
    max_ms: float
    rows: int


def enable(admin_url: str) -> None:
    """Create the extension if needed; raise ``StatementStatsUnavailable`` when it is not preloaded."""
    with psycopg.connect(admin_url, autocommit=True) as c:
        preload = c.execute("SHOW shared_preload_libraries").fetchone()[0]  # type: ignore[index]
        if "pg_stat_statements" not in preload:
            raise StatementStatsUnavailable("pg_stat_statements is not in shared_preload_libraries")
        c.execute("CREATE EXTENSION IF NOT EXISTS pg_stat_statements")


def top_statements(admin_url: str, limit: int = 10, order_by: str = "total_exec_time") -> list[StatementStat]:
    if order_by not in {"total_exec_time", "mean_exec_time", "max_exec_time", "calls"}:
        raise ValueError(f"unsupported ordering: {order_by}")
    enable(admin_url)
    with psycopg.connect(admin_url) as c:
        rows = c.execute(
            f"SELECT query, calls, total_exec_time, mean_exec_time, max_exec_time, rows "  # noqa: S608 (allowlisted)
            f"FROM pg_stat_statements WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database()) "
            f"ORDER BY {order_by} DESC LIMIT %s", (limit,)).fetchall()
    return [StatementStat(str(q), int(n), float(t), float(m), float(x), int(r)) for q, n, t, m, x, r in rows]
