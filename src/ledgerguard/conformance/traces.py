"""Extract abstract traces from the coordinator's workflow_events audit log."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import psycopg


@dataclass(frozen=True)
class TransferTrace:
    transfer_id: UUID
    final_state: str
    tokens: tuple[str, ...]


def normalize_events(rows: list[tuple[str, dict[str, object] | None]]) -> list[str]:
    """Map ordered (event_type, details) rows to specification tokens.

    ``DECISION_MADE`` carries the chosen decision, so it is split into two tokens.
    """
    tokens: list[str] = []
    for event_type, details in rows:
        if event_type == "DECISION_MADE":
            decision = str((details or {}).get("decision", "UNKNOWN"))
            tokens.append(f"DECISION_MADE:{decision}")
        else:
            tokens.append(event_type)
    return tokens


def fetch_traces(
    coord_db_url: str | None = None,
    limit: int | None = None,
    *,
    conn: psycopg.Connection[tuple[object, ...]] | None = None,
    exclude: set[UUID] | None = None,
) -> list[TransferTrace]:
    """Load one trace per transfer, ordered by (created_at, event_id).

    Pass ``conn`` to read inside an existing transaction (used by tests that inject
    corrupted history and roll it back) and ``exclude`` to skip already-known transfers.
    """
    query = """
        SELECT t.transfer_id, t.state, e.event_type, e.details
        FROM transfers t
        JOIN workflow_events e ON e.transfer_id = t.transfer_id
        ORDER BY t.transfer_id, e.created_at, e.event_id
    """
    per: dict[UUID, tuple[str, list[tuple[str, dict[str, object] | None]]]] = {}

    def _read(c: psycopg.Connection[tuple[object, ...]]) -> None:
        for tid, state, etype, details in c.execute(query):
            if exclude and tid in exclude:
                continue
            per.setdefault(tid, (str(state), []))[1].append((str(etype), details))  # type: ignore[arg-type]

    if conn is not None:
        _read(conn)
    else:
        if coord_db_url is None:
            raise ValueError("coord_db_url or conn is required")
        with psycopg.connect(coord_db_url) as own:
            _read(own)
    traces = [
        TransferTrace(tid, state, tuple(normalize_events(rows)))
        for tid, (state, rows) in per.items()
    ]
    return traces[:limit] if limit else traces


def known_transfer_ids(coord_db_url: str) -> set[UUID]:
    with psycopg.connect(coord_db_url) as conn:
        return {r[0] for r in conn.execute("SELECT transfer_id FROM transfers")}
