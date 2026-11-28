"""Query-plan assertions: the hot queries must use their intended index at realistic volume.

A plan on a nearly empty development table proves nothing (a sequential scan is the right plan
for 20 rows). So each query is planned against a throwaway schema holding *copies* of the real
tables (``LIKE ... INCLUDING ALL``, so the real indexes and CHECKs come along) loaded with tens of
thousands of rows and ``ANALYZE``d. Production tables are never written.

Every catalogued query also records where its SQL lives in the source tree, and a drift check
fails if that text changes, so the catalogue cannot silently describe queries that no longer exist.
Whole-ledger audits (hash-chain verification, full journal balance checks) are O(n) by design and
are deliberately not in this catalogue.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

import psycopg

from ledgerguard.config import settings

REPO_ROOT = Path(__file__).resolve().parents[3]
COORD, LEDGER = "coordinator", "ledger"
_INDEX_NODES = {"Index Scan", "Index Only Scan", "Bitmap Index Scan"}


@dataclass(frozen=True)
class HotQuery:
    name: str
    db: str  # COORD or LEDGER
    sql: str
    params: tuple[Any, ...]
    relation: str  # the table whose access path is asserted
    index: str  # intended index, by its name in the real schema
    source_file: str
    source_fragment: str  # text that must still appear (whitespace-normalised) in source_file
    note: str = ""


def _q(db: str, name: str, sql: str, params: tuple[Any, ...], relation: str, index: str,
       source_file: str, fragment: str, note: str = "") -> HotQuery:
    return HotQuery(name, db, sql, params, relation, index, source_file, fragment, note)


CATALOG: tuple[HotQuery, ...] = (
    # ---- coordinator ------------------------------------------------------------------------
    _q(COORD, "transfer_by_id_for_update",
       "SELECT transfer_id, state FROM transfers WHERE transfer_id = %s FOR UPDATE",
       ("{tid}",), "transfers", "transfers_pkey",
       "src/ledgerguard/worker/coordinator_service.py", "FROM transfers WHERE transfer_id = %s FOR UPDATE"),
    _q(COORD, "decision_by_transfer",
       "SELECT decision, decided_at FROM transfer_decisions WHERE transfer_id = %s",
       ("{tid}",), "transfer_decisions", "transfer_decisions_pkey",
       "src/ledgerguard/worker/orchestrator.py",
       "SELECT decision, decided_at FROM transfer_decisions WHERE transfer_id = %s"),
    _q(COORD, "api_idempotency_lookup",
       "SELECT payload_hash FROM api_idempotency "
       "WHERE idempotency_key = %s AND operation_namespace = 'TRANSFERS'",
       ("{key}",), "api_idempotency", "api_idempotency_pkey",
       "src/ledgerguard/coordinator/transfer_coordinator.py",
       "WHERE idempotency_key = %s AND operation_namespace = 'TRANSFERS'"),
    _q(COORD, "transfer_by_idempotency_key",
       "SELECT t.transfer_id FROM transfer_idempotency_claims c "
       "JOIN transfers t ON t.transfer_id = c.transfer_id WHERE c.idempotency_key = %s",
       ("{key}",), "transfer_idempotency_claims", "transfer_idempotency_claims_pkey",
       "src/ledgerguard/coordinator/idempotent_transfer.py", "WHERE c.idempotency_key = %s",
       "Replaces an unindexed scan of transfers by key."),
    _q(COORD, "open_transfer_recovery_sweep",
       "SELECT transfer_id, state FROM transfers "
       "WHERE state IN ('ACCEPTED', 'PREPARING', 'COMMITTING', 'CANCELLING') "
       "AND updated_at <= NOW() - make_interval(secs => %s) ORDER BY created_at ASC",
       (0.0,), "transfers", "idx_transfers_open_created",
       "src/ledgerguard/worker/orchestrator.py",
       "WHERE state IN ('ACCEPTED', 'PREPARING', 'COMMITTING', 'CANCELLING') "
       "AND updated_at <= NOW() - make_interval(secs => %s) ORDER BY created_at ASC",
       "Reads only unfinished transfers, independent of how many have settled; the age filter is applied after the index."),
    _q(COORD, "operator_transfer_list",
       "SELECT t.transfer_id, d.decision FROM transfers t "
       "LEFT JOIN transfer_decisions d ON t.transfer_id = d.transfer_id "
       "ORDER BY t.created_at DESC LIMIT 50",
       (), "transfers", "idx_transfers_created_desc",
       "src/ledgerguard/api/routes.py", "ORDER BY t.created_at DESC LIMIT %s"),
    _q(COORD, "workflow_timeline",
       "SELECT event_id, event_type FROM workflow_events WHERE transfer_id = %s ORDER BY created_at ASC",
       ("{tid}",), "workflow_events", "uq_workflow_events_transfer_event",
       "src/ledgerguard/api/routes.py", "FROM workflow_events WHERE transfer_id = %s ORDER BY created_at ASC"),
    _q(COORD, "outbox_claim",
       "SELECT outbox_id FROM outbox_events WHERE next_attempt_at <= NOW() AND delivered_at IS NULL "
       "ORDER BY next_attempt_at ASC LIMIT 20 FOR UPDATE SKIP LOCKED",
       (), "outbox_events", "idx_outbox_pending",
       "src/ledgerguard/worker/outbox.py",
       "WHERE next_attempt_at <= NOW() AND delivered_at IS NULL ORDER BY next_attempt_at ASC LIMIT %s"),
    _q(COORD, "outbox_claim_for_aggregate",
       "SELECT outbox_id FROM outbox_events WHERE next_attempt_at <= NOW() AND delivered_at IS NULL "
       "AND aggregate_id = %s ORDER BY next_attempt_at ASC LIMIT 20 FOR UPDATE SKIP LOCKED",
       ("{aggregate}",), "outbox_events", "idx_outbox_pending",
       "src/ledgerguard/worker/outbox.py", "AND aggregate_id = %s ORDER BY next_attempt_at ASC"),
    # ---- ledger -----------------------------------------------------------------------------
    _q(LEDGER, "statement_first_page",
       "SELECT l.account_sequence, h.currency FROM journal_lines l "
       "JOIN journal_headers h ON l.journal_id = h.journal_id WHERE l.account_id = %s "
       "ORDER BY l.account_sequence ASC LIMIT 51",
       ("{account}",), "journal_lines", "uq_account_sequence",
       "src/ledgerguard/participant/account_service.py", "ORDER BY l.account_sequence ASC LIMIT %s"),
    _q(LEDGER, "statement_after_cursor",
       "SELECT l.account_sequence, h.currency FROM journal_lines l "
       "JOIN journal_headers h ON l.journal_id = h.journal_id WHERE l.account_id = %s "
       "AND l.account_sequence > 40 ORDER BY l.account_sequence ASC LIMIT 51",
       ("{account}",), "journal_lines", "uq_account_sequence",
       "src/ledgerguard/participant/account_service.py", 'query += " AND l.account_sequence > %s"'),
    _q(LEDGER, "ledger_idempotency_lookup",
       "SELECT payload_hash, response_body FROM idempotency_records "
       "WHERE idempotency_key = %s AND operation_namespace = %s",
       ("{key}", "local_transfer"), "idempotency_records", "idempotency_records_pkey",
       "src/ledgerguard/participant/transfer_service.py",
       "FROM idempotency_records WHERE idempotency_key = %s AND operation_namespace = %s"),
    _q(LEDGER, "local_transfer_by_id",
       "SELECT transfer_id FROM local_transfers WHERE transfer_id = %s FOR UPDATE",
       ("{tid}",), "local_transfers", "local_transfers_pkey",
       "src/ledgerguard/participant/transfer_service.py",
       "FROM local_transfers WHERE transfer_id = %s FOR UPDATE"),
    _q(LEDGER, "intent_by_transfer",
       "SELECT intent_id, status FROM transfer_intents WHERE transfer_id = %s",
       ("{tid}",), "transfer_intents", "transfer_intents_transfer_id_key",
       "src/ledgerguard/participant/workflow_handler.py", "FROM transfer_intents WHERE transfer_id = %s",
       "Served by the unique constraint; the duplicate plain index was dropped."),
    _q(LEDGER, "hold_by_transfer",
       "SELECT hold_id, status FROM holds WHERE transfer_id = %s",
       ("{tid}",), "holds", "holds_transfer_id_key",
       "src/ledgerguard/participant/workflow_handler.py", "FROM holds WHERE transfer_id = %s"),
    _q(LEDGER, "inbox_by_command",
       "SELECT result FROM command_inbox WHERE command_id = %s",
       ("{command}",), "command_inbox", "command_inbox_pkey",
       "src/ledgerguard/participant/workflow_handler.py", "SELECT result FROM command_inbox WHERE command_id = %s"),
    _q(LEDGER, "holds_as_of",
       "SELECT hold_id, status FROM holds WHERE account_id = %s AND created_at <= NOW() "
       "ORDER BY created_at ASC",
       ("{account}",), "holds", "idx_holds_account_created",
       "src/ledgerguard/history/reconstruction.py",
       "WHERE account_id = %s AND created_at <= %s ORDER BY created_at ASC",
       "Previously only the ACTIVE-holds partial index existed, so released holds were scanned."),
    _q(LEDGER, "journal_headers_from_sequence",
       "SELECT sequence_number, entry_hash FROM journal_headers WHERE sequence_number >= 49000 "
       "ORDER BY sequence_number ASC",
       (), "journal_headers", "journal_headers_sequence_number_key",
       "src/ledgerguard/audit/journal_chain.py",
       "WHERE sequence_number >= %s ORDER BY sequence_number ASC"),
)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def check_source_drift(query: HotQuery) -> bool:
    """True when the recorded fragment is still present in the recorded source file."""
    src = (REPO_ROOT / query.source_file).read_text(encoding="utf-8")
    return _norm(query.source_fragment) in _norm(src)


# --------------------------------------------------------------------------------------------
# Volume loading
# --------------------------------------------------------------------------------------------

N_TRANSFERS = 60_000
N_OUTBOX = 60_000
N_LINES = 100_000
N_ACCOUNTS = 500
N_HOLDS = 60_000


class ScratchVolume:
    """Copies of the real tables, loaded with data, in a throwaway schema."""

    def __init__(self, db: str) -> None:
        self.db = db
        self.url = settings.coordinator_admin_db_url if db == COORD else settings.ledger1_admin_db_url
        self.schema = f"plan_study_{uuid4().hex[:10]}"
        self.ids: dict[str, str] = {}

    def __enter__(self) -> ScratchVolume:
        with psycopg.connect(self.url, autocommit=True) as c:
            c.execute(f"CREATE SCHEMA {self.schema}")
            if self.db == COORD:
                self._load_coordinator(c)
            else:
                self._load_ledger(c)
        return self

    def __exit__(self, *exc: object) -> None:
        with psycopg.connect(self.url, autocommit=True) as c:
            c.execute(f"DROP SCHEMA IF EXISTS {self.schema} CASCADE")

    def _copy(self, c: psycopg.Connection, *tables: str) -> None:
        for t in tables:
            c.execute(f"CREATE TABLE {self.schema}.{t} (LIKE public.{t} INCLUDING ALL)")

    def _analyze(self, c: psycopg.Connection, *tables: str) -> None:
        for t in tables:
            c.execute(f"ANALYZE {self.schema}.{t}")

    def _load_coordinator(self, c: psycopg.Connection) -> None:
        s = self.schema
        tabs = ("transfers", "transfer_decisions", "workflow_events", "api_idempotency",
                "outbox_events", "transfer_idempotency_claims")
        self._copy(c, *tabs)
        # 1 in 200 transfers is still open; the rest settled long ago (the realistic shape).
        c.execute(f"""
            INSERT INTO {s}.transfers (transfer_id, idempotency_key, source_account_id,
                destination_account_id, amount_minor, transfer_type, source_ledger_id,
                destination_ledger_id, state, created_at)
            SELECT md5('t'||i)::uuid, 'k'||i, md5('s'||(i % 700))::uuid, md5('d'||(i % 700))::uuid,
                   100, 'CROSS_LEDGER', 'ledger-1', 'ledger-2',
                   CASE WHEN i % 200 = 0 THEN 'COMMITTING' ELSE 'SETTLED' END,
                   now() - (i * interval '1 second')
            FROM generate_series(1, {N_TRANSFERS}) i""")
        c.execute(f"""INSERT INTO {s}.transfer_decisions (transfer_id, decision)
            SELECT transfer_id, 'COMMIT' FROM {s}.transfers""")
        c.execute(f"""INSERT INTO {s}.transfer_idempotency_claims (idempotency_key, transfer_id)
            SELECT idempotency_key, transfer_id FROM {s}.transfers""")
        c.execute(f"""INSERT INTO {s}.workflow_events (transfer_id, event_type, created_at)
            SELECT transfer_id, e, created_at FROM {s}.transfers,
                   unnest(ARRAY['PREPARED','SETTLED']) e""")
        c.execute(f"""INSERT INTO {s}.api_idempotency (idempotency_key, operation_namespace,
                payload_hash, status_code, response_body)
            SELECT 'k'||i, 'TRANSFERS', md5(i::text), 200, '{{}}'::jsonb
            FROM generate_series(1, {N_TRANSFERS}) i""")
        # Outbox: almost everything delivered; a few hundred pending (the steady state).
        c.execute(f"""INSERT INTO {s}.outbox_events (aggregate_id, event_type, payload,
                next_attempt_at, delivered_at, created_at)
            SELECT CASE WHEN i % 200 = 0 THEN 'agg-pending-'||i ELSE 'agg-'||i END, 'DISPATCH_PREPARE',
                   '{{}}'::jsonb, now() - interval '1 minute',
                   CASE WHEN i % 200 = 0 THEN NULL ELSE now() END, now()
            FROM generate_series(1, {N_OUTBOX}) i""")
        self._analyze(c, *tabs)
        self.ids = {"tid": str(c.execute("SELECT md5('t12345')::uuid").fetchone()[0]),  # type: ignore[index]
                    "key": "k12345", "aggregate": "agg-pending-200"}

    def _load_ledger(self, c: psycopg.Connection) -> None:
        s = self.schema
        tabs = ("journal_headers", "journal_lines", "holds", "command_inbox", "transfer_intents",
                "idempotency_records", "local_transfers")
        self._copy(c, *tabs)
        n_headers = N_LINES // 2
        c.execute(f"""INSERT INTO {s}.journal_headers (journal_id, operation_type, sequence_number,
                transfer_id, created_at)
            SELECT md5('j'||i)::uuid, 'LOCAL_TRANSFER', i + 1, md5('t'||i)::uuid,
                   now() - (i * interval '1 second')
            FROM generate_series(0, {n_headers - 1}) i""")
        c.execute(f"""INSERT INTO {s}.journal_lines (journal_id, line_no, account_id, side,
                amount_minor, account_sequence)
            SELECT md5('j'||(i / 2))::uuid, (i % 2) + 1, md5('a'||(i % {N_ACCOUNTS}))::uuid,
                   CASE WHEN i % 2 = 0 THEN 'DEBIT' ELSE 'CREDIT' END, 100, (i / {N_ACCOUNTS}) + 1
            FROM generate_series(0, {N_LINES - 1}) i""")
        c.execute(f"""INSERT INTO {s}.holds (account_id, transfer_id, amount_minor, status, created_at)
            SELECT md5('a'||(i % {N_ACCOUNTS}))::uuid, md5('t'||i)::uuid, 100,
                   CASE WHEN i % 300 = 0 THEN 'ACTIVE' ELSE 'RELEASED' END,
                   now() - (i * interval '1 second')
            FROM generate_series(1, {N_HOLDS}) i""")
        c.execute(f"""INSERT INTO {s}.transfer_intents (transfer_id, direction, source_account_id,
                destination_account_id, amount_minor, status)
            SELECT md5('t'||i)::uuid, 'OUTGOING', md5('a'||(i % {N_ACCOUNTS}))::uuid,
                   md5('a'||((i + 1) % {N_ACCOUNTS}))::uuid, 100, 'CONFIRMED'
            FROM generate_series(1, {N_HOLDS}) i""")
        c.execute(f"""INSERT INTO {s}.command_inbox (command_id, transfer_id, command_type,
                payload_hash, result)
            SELECT 'cmd-'||i, md5('t'||i)::uuid, 'SOURCE_PREPARE', md5(i::text), '{{}}'::jsonb
            FROM generate_series(1, {N_HOLDS}) i""")
        c.execute(f"""INSERT INTO {s}.idempotency_records (idempotency_key, operation_namespace,
                payload_hash, status_code, response_body)
            SELECT 'k'||i, 'local_transfer', md5(i::text), 200, '{{}}'::jsonb
            FROM generate_series(1, {N_HOLDS}) i""")
        c.execute(f"""INSERT INTO {s}.local_transfers (transfer_id, idempotency_key, payload_hash,
                source_account_id, destination_account_id, amount_minor, journal_id)
            SELECT md5('t'||i)::uuid, 'lt'||i, md5(i::text), md5('a'||(i % {N_ACCOUNTS}))::uuid,
                   md5('a'||((i + 1) % {N_ACCOUNTS}))::uuid, 100, md5('j'||i)::uuid
            FROM generate_series(1, 20000) i""")
        self._analyze(c, *tabs)
        self.ids = {"tid": str(c.execute("SELECT md5('t12345')::uuid").fetchone()[0]),  # type: ignore[index]
                    "key": "k12345", "command": "cmd-12345",
                    "account": str(c.execute("SELECT md5('a7')::uuid").fetchone()[0])}  # type: ignore[index]


# --------------------------------------------------------------------------------------------
# Planning
# --------------------------------------------------------------------------------------------


@dataclass
class PlanResult:
    query: HotQuery
    nodes: list[dict[str, Any]] = field(default_factory=list)
    index_used: str | None = None
    seq_scan_on_relation: bool = False
    planning_ms: float = 0.0


def _walk(node: dict[str, Any], out: list[dict[str, Any]]) -> None:
    out.append(node)
    for child in node.get("Plans", []):
        _walk(child, out)


def explain(vol: ScratchVolume, query: HotQuery) -> PlanResult:
    """Plan ``query`` against the loaded copies (client-side binding, never executed)."""
    params = tuple(vol.ids[p[1:-1]] if isinstance(p, str) and p.startswith("{") else p
                   for p in query.params)
    with psycopg.connect(vol.url, autocommit=True) as conn:
        conn.execute(f"SET search_path = {vol.schema}")
        cur = psycopg.ClientCursor(conn)
        cur.execute("EXPLAIN (FORMAT JSON) " + query.sql, params)
        doc = cur.fetchone()[0][0]  # type: ignore[index]
        nodes: list[dict[str, Any]] = []
        _walk(doc["Plan"], nodes)
        relation_nodes = [n for n in nodes if n.get("Relation Name") == query.relation]
        seq = any(n["Node Type"] == "Seq Scan" for n in relation_nodes)
        used = next((n["Index Name"] for n in nodes
                     if n["Node Type"] in _INDEX_NODES and "Index Name" in n
                     and (n.get("Relation Name") == query.relation
                          or n["Node Type"] == "Bitmap Index Scan")), None)
    return PlanResult(query=query, nodes=nodes, index_used=used, seq_scan_on_relation=seq,
                      planning_ms=float(doc.get("Planning Time", 0.0)))


def index_definition(url: str, schema: str, index_name: str) -> str | None:
    """Schema- and name-independent text of an index (for comparing scratch vs real)."""
    with psycopg.connect(url) as c:
        row = c.execute("SELECT indexdef FROM pg_indexes WHERE schemaname = %s AND indexname = %s",
                        (schema, index_name)).fetchone()
    return _strip_def(row[0]) if row else None


def _strip_def(defn: str) -> str:
    defn = re.sub(r"^CREATE (UNIQUE )?INDEX \S+ ON ", "", defn)
    return re.sub(r"\b(public|plan_study_[0-9a-f]+)\.", "", defn)


def scratch_index_definition(vol: ScratchVolume, index_name: str) -> str | None:
    with psycopg.connect(vol.url) as c:
        row = c.execute("SELECT indexdef FROM pg_indexes WHERE schemaname = %s AND indexname = %s",
                        (vol.schema, index_name)).fetchone()
    return _strip_def(row[0]) if row else None


def used_index_matches_intended(vol: ScratchVolume, result: PlanResult) -> bool:
    """The index the planner chose has the same definition as the intended real index."""
    if result.index_used is None:
        return False
    real = index_definition(vol.url, "public", result.query.index)
    used = scratch_index_definition(vol, result.index_used)
    return real is not None and used is not None and real.replace("UNIQUE ", "") == used.replace("UNIQUE ", "")


# --------------------------------------------------------------------------------------------
# Redundant-index detection
# --------------------------------------------------------------------------------------------


def find_redundant_indexes(url: str, schema: str = "public") -> list[tuple[str, str, str]]:
    """Return ``(table, redundant_index, covering_index)`` for indexes that add only write cost.

    An index is redundant when another non-partial index on the same table starts with all of its
    columns (identical column lists included), so the planner can always use the other one.
    """
    sql = """
        SELECT t.relname, i.relname, ix.indisunique, ix.indisprimary,
               ix.indpred IS NOT NULL AS partial, ix.indexprs IS NOT NULL AS expr,
               (SELECT array_agg(a.attname ORDER BY k.ord)
                  FROM unnest(ix.indkey::int2[]) WITH ORDINALITY k(attnum, ord)
                  JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = k.attnum) AS cols,
               ix.indisvalid
        FROM pg_index ix
        JOIN pg_class i ON i.oid = ix.indexrelid
        JOIN pg_class t ON t.oid = ix.indrelid
        JOIN pg_namespace n ON n.oid = t.relnamespace
        WHERE n.nspname = %s AND t.relkind = 'r'
    """
    with psycopg.connect(url) as c:
        rows = c.execute(sql, (schema,)).fetchall()
    found: list[tuple[str, str, str]] = []
    for table, name, unique, primary, partial, expr, cols, valid in rows:
        if partial or expr or not valid or primary or unique:
            continue  # a unique/primary index also enforces a rule, so it is never "redundant"
        for t2, n2, u2, p2, part2, expr2, cols2, valid2 in rows:
            if t2 != table or n2 == name or part2 or expr2 or not valid2:
                continue
            if cols2[: len(cols)] == cols and (
                len(cols2) > len(cols) or u2 or p2 or (cols2 == cols and n2 < name)
            ):
                found.append((table, name, n2))
                break
    return found


def explain_without_index(vol: ScratchVolume, query: HotQuery) -> PlanResult:
    """Negative control: drop the intended index from the *scratch copy* and plan again."""
    real = index_definition(vol.url, "public", query.index)
    with psycopg.connect(vol.url, autocommit=True) as c:
        names = [r[0] for r in c.execute(
            "SELECT indexname FROM pg_indexes WHERE schemaname = %s AND tablename = %s",
            (vol.schema, query.relation)).fetchall()]
        for name in names:
            if real and (scratch_index_definition(vol, name) or "").replace("UNIQUE ", "") == real.replace("UNIQUE ", ""):
                c.execute(f"DROP INDEX {vol.schema}.{name}") if not _is_constraint(c, vol.schema, name) \
                    else c.execute(f"ALTER TABLE {vol.schema}.{query.relation} DROP CONSTRAINT {name}")
    return explain(vol, query)


def _is_constraint(conn: psycopg.Connection, schema: str, index_name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace "
        "WHERE n.nspname = %s AND c.conname = %s", (schema, index_name)).fetchone() is not None


__all__ = ["CATALOG", "COORD", "LEDGER", "HotQuery", "PlanResult", "ScratchVolume",
           "check_source_drift", "explain", "explain_without_index", "find_redundant_indexes",
           "used_index_matches_intended"]
