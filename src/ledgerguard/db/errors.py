"""Classify database errors as infrastructure failures versus business rejections.

A business rejection (unbalanced journal, closed account, constraint violation) is the client's
problem and maps to a 4xx. An infrastructure failure (disk full, out of memory, too many
connections, server shutdown or crash, I/O error, lost connection, lock/serialization/deadlock
failure) says nothing about the request: it must surface as a retryable 503 and never be reported
as "your request is invalid" or leak server detail.

Note SQLSTATE class 55 mixes both: ``55000`` (object not in prerequisite state, used for CLOSED
accounts and journal immutability) is a business error; ``55P03`` (lock timeout) is infrastructure.
"""

from __future__ import annotations

import psycopg

_INFRASTRUCTURE_CLASSES = frozenset({"08", "40", "53", "57", "58"})
_INFRASTRUCTURE_STATES = frozenset({"55P03"})


def is_infrastructure_error(exc: BaseException) -> bool:
    if not isinstance(exc, psycopg.Error):
        return False
    state = exc.sqlstate
    if state is None:  # no server response: connect failure, dropped socket, timeout
        return isinstance(exc, psycopg.OperationalError)
    return state[:2] in _INFRASTRUCTURE_CLASSES or state in _INFRASTRUCTURE_STATES
