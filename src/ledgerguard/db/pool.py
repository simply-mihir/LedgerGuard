"""Database connection pool management using psycopg 3."""

import logging
from collections.abc import Generator
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)

# Connection pools keyed by database URL
_pools: dict[str, ConnectionPool] = {}


def get_connection_pool(db_url: str, min_size: int = 2, max_size: int = 15) -> ConnectionPool:
    """Return or create a connection pool for a specific database URL."""
    if db_url not in _pools:
        logger.info("Initializing connection pool for %s", db_url.split("@")[-1])
        _pools[db_url] = ConnectionPool(
            conninfo=db_url,
            min_size=min_size,
            max_size=max_size,
            open=True,
            kwargs={"row_factory": dict_row},
        )
    return _pools[db_url]


def close_all_pools() -> None:
    """Close all active connection pools."""
    for url, pool in _pools.items():
        try:
            pool.close()
        except Exception as e:
            logger.warning("Error closing pool %s: %s", url.split("@")[-1], e)
    _pools.clear()


@contextmanager
def get_db_connection(db_url: str) -> Generator[psycopg.Connection, None, None]:
    """Provide a connection from the pool as a context manager."""
    pool = get_connection_pool(db_url)
    with pool.connection() as conn:
        yield conn
