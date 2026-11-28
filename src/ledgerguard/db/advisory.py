"""Cluster-wide singletons via PostgreSQL session advisory locks.

The lock lives on a dedicated autocommit connection, so no transaction is open while the holder works
(a held lock is not a held transaction), and PostgreSQL releases it if the holder's connection or
process dies - there is no stale-lock cleanup to get wrong.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import psycopg


@contextmanager
def singleton(db_url: str, name: str) -> Iterator[bool]:
    """Yield True if this caller now holds the named lock, False if another holder has it."""
    with psycopg.connect(db_url, autocommit=True) as conn:
        got = bool(conn.execute("SELECT pg_try_advisory_lock(hashtextextended(%s, 0))", (name,)).fetchone()[0])  # type: ignore[index]
        try:
            yield got
        finally:
            if got:
                conn.execute("SELECT pg_advisory_unlock(hashtextextended(%s, 0))", (name,))
