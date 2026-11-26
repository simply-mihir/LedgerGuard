"""Bounded transaction retry for PostgreSQL transient concurrency errors (40P01, 40001)."""

from __future__ import annotations

import logging
import random
import threading
import time
from collections.abc import Callable

import psycopg

from ledgerguard.config import settings
from ledgerguard.observability import safe_span

logger = logging.getLogger(__name__)

_TRANSIENT_SQLSTATES = frozenset({"40P01", "40001"})

_retry_lock = threading.Lock()
_retry_counts: dict[str, int] = {"40P01": 0, "40001": 0}


class TransientRetryExhaustedError(Exception):
    """Raised when bounded retries for a transient PostgreSQL concurrency error are exhausted."""

    def __init__(self, operation_name: str, sqlstate: str, attempts: int, cause: Exception) -> None:
        super().__init__(
            f"Transient concurrency retries exhausted for {operation_name} "
            f"(sqlstate={sqlstate}, attempts={attempts})"
        )
        self.operation_name = operation_name
        self.sqlstate = sqlstate
        self.attempts = attempts
        self.__cause__ = cause


def get_transient_retry_stats() -> dict[str, int]:
    """Return thread-safe snapshot of internal transient retry counts."""
    with _retry_lock:
        return dict(_retry_counts)


def _extract_transient_sqlstate(exc: BaseException) -> str | None:
    if isinstance(exc, psycopg.errors.DeadlockDetected):
        return "40P01"
    if isinstance(exc, psycopg.errors.SerializationFailure):
        return "40001"
    sqlstate = getattr(exc, "sqlstate", None)
    if isinstance(sqlstate, str) and sqlstate in _TRANSIENT_SQLSTATES:
        return sqlstate
    return None


def run_with_transient_retry[T](
    fn: Callable[[], T],
    *,
    operation_name: str,
    max_retries: int | None = None,
    base_delay_ms: float | None = None,
    max_delay_ms: float | None = None,
) -> T:
    """Execute a complete local transaction boundary with bounded retry on 40P01/40001 only.

    Never retries validation errors, insufficient funds, invariant violations,
    permanent DB errors, or unclassified exceptions.
    """
    retries = settings.db_transient_max_retries if max_retries is None else max_retries
    base_ms = settings.db_transient_base_backoff_ms if base_delay_ms is None else base_delay_ms
    cap_ms = settings.db_transient_max_backoff_ms if max_delay_ms is None else max_delay_ms

    attempt = 0
    while True:
        try:
            return fn()
        except Exception as exc:
            sqlstate = _extract_transient_sqlstate(exc)
            if sqlstate is None:
                raise

            if attempt >= retries:
                raise TransientRetryExhaustedError(operation_name, sqlstate, attempt + 1, exc) from exc

            attempt += 1
            with _retry_lock:
                _retry_counts[sqlstate] = _retry_counts.get(sqlstate, 0) + 1

            exp_ms = min(cap_ms, base_ms * (2 ** (attempt - 1)))
            delay_ms = round(random.uniform(exp_ms * 0.5, exp_ms), 2)
            logger.warning(
                "Retrying transient PostgreSQL error operation=%s sqlstate=%s attempt=%d delay_ms=%.2f",
                operation_name,
                sqlstate,
                attempt,
                delay_ms,
            )
            with safe_span(
                "db.transient_retry",
                attributes={
                    "operation.type": operation_name,
                    "db.sqlstate": sqlstate,
                    "retry.attempt": attempt,
                    "retry.delay_ms": delay_ms,
                },
            ):
                time.sleep(delay_ms / 1000.0)
