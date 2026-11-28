"""Evidence for the journal-partitioning decision, measured on a throwaway schema.

The question is whether ``journal_headers`` / ``journal_lines`` can be natively partitioned without
weakening an invariant the ledger relies on. Each probe builds the partitioned shape in a scratch
schema (dropped afterwards), so nothing here touches posted journal history.

Probes (each returns a :class:`Finding`):

* ``unique_needs_partition_key``  - PostgreSQL refuses the real PRIMARY KEY / UNIQUE(sequence_number)
  / FK targets on a table partitioned by ``created_at``.
* ``compliant_shape_loses_global_uniqueness`` - the shape PostgreSQL does accept lets two journals
  share a ``sequence_number`` (and a ``journal_id``) if they land in different partitions; the
  unpartitioned table rejects both with 23505.
* ``lines_lookup_fans_out`` - hash-partitioning ``journal_lines`` by ``account_id`` (the only key that
  keeps ``UNIQUE(account_id, account_sequence)``) makes the balanced-journal trigger's
  ``WHERE journal_id = ?`` probe every partition.
* ``partition_drop_bypasses_immutability`` - ``DROP``/``DETACH`` of a partition is not stopped by the
  row and TRUNCATE immutability triggers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import psycopg
from psycopg import errors

from ledgerguard.config import settings

HASH_PARTITIONS = 8


@dataclass
class Finding:
    probe: str
    holds: bool  # True when the observation supports "native partitioning weakens the ledger".
    summary: str
    detail: dict[str, Any] = field(default_factory=dict)


def _scanned_relations(plan: dict[str, Any]) -> set[str]:
    found: set[str] = set()

    def walk(node: dict[str, Any]) -> None:
        if "Relation Name" in node:
            found.add(node["Relation Name"])
        for child in node.get("Plans", []):
            walk(child)

    walk(plan)
    return found


def _explain(c: psycopg.Connection, sql: str) -> dict[str, Any]:
    cur = psycopg.ClientCursor(c)
    cur.execute("EXPLAIN (FORMAT JSON) " + sql)
    plan: dict[str, Any] = cur.fetchone()[0][0]["Plan"]  # type: ignore[index]
    return plan


class _Scratch:
    def __init__(self) -> None:
        self.schema = f"partition_study_{uuid4().hex[:10]}"

    def __enter__(self) -> psycopg.Connection:
        self.conn = psycopg.connect(settings.ledger1_admin_db_url, autocommit=True)
        self.conn.execute(f"CREATE SCHEMA {self.schema}")
        self.conn.execute(f"SET search_path = {self.schema}, public")
        return self.conn

    def __exit__(self, *exc: object) -> None:
        try:
            self.conn.execute(f"DROP SCHEMA IF EXISTS {self.schema} CASCADE")
        finally:
            self.conn.close()


def _sqlstate(exc: BaseException) -> str:
    return getattr(exc, "sqlstate", None) or "?"


def unique_needs_partition_key() -> Finding:
    """The real constraints cannot be created on a table partitioned by created_at."""
    attempts: dict[str, str] = {}
    with _Scratch() as c:
        for name, ddl in (
            ("primary_key_journal_id",
             "CREATE TABLE h1 (journal_id uuid PRIMARY KEY, created_at timestamptz NOT NULL) "
             "PARTITION BY RANGE (created_at)"),
            ("unique_sequence_number",
             "CREATE TABLE h2 (journal_id uuid, sequence_number bigint UNIQUE, "
             "created_at timestamptz NOT NULL) PARTITION BY RANGE (created_at)"),
        ):
            try:
                c.execute(ddl)
                attempts[name] = "ACCEPTED"
            except psycopg.Error as exc:
                attempts[name] = f"REFUSED {_sqlstate(exc)}"
        # A foreign key to journal_id needs a unique constraint on exactly journal_id.
        c.execute("CREATE TABLE h3 (journal_id uuid, created_at timestamptz NOT NULL, "
                  "PRIMARY KEY (journal_id, created_at)) PARTITION BY RANGE (created_at)")
        c.execute("CREATE TABLE l3 (line_id uuid PRIMARY KEY, journal_id uuid NOT NULL)")
        try:
            c.execute("ALTER TABLE l3 ADD FOREIGN KEY (journal_id) REFERENCES h3 (journal_id)")
            attempts["lines_fk_to_journal_id"] = "ACCEPTED"
        except psycopg.Error as exc:
            attempts["lines_fk_to_journal_id"] = f"REFUSED {_sqlstate(exc)}"
    refused = all(v.startswith("REFUSED") for v in attempts.values())
    return Finding(
        "unique_needs_partition_key", refused,
        "PostgreSQL refuses PRIMARY KEY(journal_id), UNIQUE(sequence_number) and an FK to "
        "journal_id on a table partitioned by created_at.", {"attempts": attempts})


def compliant_shape_loses_global_uniqueness() -> Finding:
    """The accepted shape (key includes created_at) no longer rejects duplicates across partitions."""
    out: dict[str, str] = {}
    jid = uuid4()
    with _Scratch() as c:
        c.execute("CREATE TABLE plain (journal_id uuid PRIMARY KEY, sequence_number bigint UNIQUE, "
                  "created_at timestamptz NOT NULL)")
        c.execute("CREATE TABLE part (journal_id uuid, sequence_number bigint, "
                  "created_at timestamptz NOT NULL, PRIMARY KEY (journal_id, created_at), "
                  "UNIQUE (sequence_number, created_at)) PARTITION BY RANGE (created_at)")
        c.execute("CREATE TABLE part_jan PARTITION OF part FOR VALUES FROM ('2026-01-01') TO ('2026-02-01')")
        c.execute("CREATE TABLE part_feb PARTITION OF part FOR VALUES FROM ('2026-02-01') TO ('2026-03-01')")
        for table, ts_pair in (("plain", ("2026-01-10", "2026-02-10")),
                               ("part", ("2026-01-10", "2026-02-10"))):
            c.execute(f"INSERT INTO {table} VALUES (%s, 1, %s)", (jid, ts_pair[0]))
            for label, row in (("duplicate_journal_id", (jid, 2, ts_pair[1])),
                               ("duplicate_sequence_number", (uuid4(), 1, ts_pair[1]))):
                try:
                    c.execute(f"INSERT INTO {table} VALUES (%s, %s, %s)", row)
                    out[f"{table}.{label}"] = "ACCEPTED"
                except errors.UniqueViolation:
                    out[f"{table}.{label}"] = "REJECTED 23505"
    weakened = (out["plain.duplicate_journal_id"] == "REJECTED 23505"
                and out["plain.duplicate_sequence_number"] == "REJECTED 23505"
                and out["part.duplicate_journal_id"] == "ACCEPTED"
                and out["part.duplicate_sequence_number"] == "ACCEPTED")
    return Finding(
        "compliant_shape_loses_global_uniqueness", weakened,
        "With the partition key in the unique constraints, a duplicate journal_id or "
        "sequence_number in another partition is accepted; the unpartitioned table rejects both.",
        {"results": out})


def lines_lookup_fans_out() -> Finding:
    """Hash partitioning lines by account_id keeps UNIQUE(account_id, seq) but not journal lookups."""
    with _Scratch() as c:
        c.execute("CREATE TABLE plain_lines (line_id uuid PRIMARY KEY, journal_id uuid NOT NULL, "
                  "account_id uuid NOT NULL, account_sequence bigint NOT NULL, "
                  "UNIQUE (account_id, account_sequence))")
        c.execute("CREATE INDEX ON plain_lines (journal_id)")
        c.execute("CREATE TABLE part_lines (line_id uuid, journal_id uuid NOT NULL, "
                  "account_id uuid NOT NULL, account_sequence bigint NOT NULL, "
                  "PRIMARY KEY (line_id, account_id), UNIQUE (account_id, account_sequence)) "
                  "PARTITION BY HASH (account_id)")
        for i in range(HASH_PARTITIONS):
            c.execute(f"CREATE TABLE part_lines_{i} PARTITION OF part_lines "
                      f"FOR VALUES WITH (MODULUS {HASH_PARTITIONS}, REMAINDER {i})")
        c.execute("CREATE INDEX ON part_lines (journal_id)")
        for t in ("plain_lines", "part_lines"):
            c.execute(f"""
                INSERT INTO {t} (line_id, journal_id, account_id, account_sequence)
                SELECT md5('l'||i)::uuid, md5('j'||(i/2))::uuid, md5('a'||(i % 400))::uuid, i
                FROM generate_series(1, 40000) i""")
            c.execute(f"ANALYZE {t}")
        jid = c.execute("SELECT md5('j'||100)::uuid").fetchone()[0]  # type: ignore[index]
        acct = c.execute("SELECT md5('a'||7)::uuid").fetchone()[0]  # type: ignore[index]
        probes = {
            "by_journal_id": f"SELECT * FROM {{t}} WHERE journal_id = '{jid}'",
            "by_account_id": f"SELECT * FROM {{t}} WHERE account_id = '{acct}' AND account_sequence = 7",
        }
        touched: dict[str, dict[str, int]] = {}
        for name, template in probes.items():
            touched[name] = {
                "unpartitioned": len(_scanned_relations(_explain(c, template.format(t="plain_lines")))),
                "partitioned": len({r for r in _scanned_relations(_explain(c, template.format(t="part_lines")))
                                    if r.startswith("part_lines_")}),
            }
    fan_out = (touched["by_journal_id"]["partitioned"] == HASH_PARTITIONS
               and touched["by_account_id"]["partitioned"] == 1)
    return Finding(
        "lines_lookup_fans_out", fan_out,
        f"Lookups by journal_id (the balanced-journal trigger and the hash-chain sealer) probe all "
        f"{HASH_PARTITIONS} partitions; only account-keyed lookups prune to one.",
        {"relations_touched": touched, "partitions": HASH_PARTITIONS})


def partition_drop_bypasses_immutability() -> Finding:
    """The row and TRUNCATE triggers do not fire for DROP or DETACH of a partition."""
    outcome: dict[str, str] = {}
    with _Scratch() as c:
        c.execute("""
            CREATE FUNCTION reject() RETURNS trigger LANGUAGE plpgsql AS
            $$ BEGIN RAISE EXCEPTION 'immutable' USING ERRCODE = '55000'; END $$""")
        c.execute("CREATE TABLE j (journal_id uuid, created_at timestamptz NOT NULL, "
                  "PRIMARY KEY (journal_id, created_at)) PARTITION BY RANGE (created_at)")
        c.execute("CREATE TRIGGER t_row BEFORE UPDATE OR DELETE ON j FOR EACH ROW EXECUTE FUNCTION reject()")
        c.execute("CREATE TRIGGER t_trunc BEFORE TRUNCATE ON j FOR EACH STATEMENT EXECUTE FUNCTION reject()")
        for m in ("01", "02", "03"):
            c.execute(f"CREATE TABLE j_{m} PARTITION OF j FOR VALUES FROM ('2026-{m}-01') "
                      f"TO ('2026-{int(m) + 1:02d}-01')")
            c.execute(f"INSERT INTO j VALUES (gen_random_uuid(), '2026-{m}-15')")
        for label, stmt in (("delete_row", "DELETE FROM j"), ("truncate", "TRUNCATE j")):
            try:
                c.execute(stmt)
                outcome[label] = "ALLOWED"
            except psycopg.Error as exc:
                outcome[label] = f"BLOCKED {_sqlstate(exc)}"
        c.execute("ALTER TABLE j DETACH PARTITION j_01")
        outcome["detach_partition"] = "ALLOWED"
        c.execute("DROP TABLE j_02")
        outcome["drop_partition"] = "ALLOWED"
        remaining = c.execute("SELECT count(*) FROM j").fetchone()[0]  # type: ignore[index]
        outcome["rows_left_after"] = str(remaining)
    bypass = (outcome["delete_row"].startswith("BLOCKED") and outcome["truncate"].startswith("BLOCKED")
              and outcome["detach_partition"] == "ALLOWED" and outcome["drop_partition"] == "ALLOWED")
    return Finding(
        "partition_drop_bypasses_immutability", bypass,
        "DELETE and TRUNCATE are blocked by the immutability triggers, but DETACH PARTITION and "
        "DROP of a partition remove history without firing either.", {"outcome": outcome})


PROBES = (
    unique_needs_partition_key,
    compliant_shape_loses_global_uniqueness,
    lines_lookup_fans_out,
    partition_drop_bypasses_immutability,
)


def run_partition_study() -> list[Finding]:
    return [probe() for probe in PROBES]


def report_markdown(findings: list[Finding], server_version: str) -> str:
    lines = [
        "# Journal partitioning study", "",
        f"PostgreSQL {server_version}. Every probe runs in a throwaway schema; no ledger table is touched.", "",
        "| Probe | Supports 'partitioning weakens the ledger' | Summary |",
        "|---|---|---|",
    ]
    for f in findings:
        lines.append(f"| `{f.probe}` | {'yes' if f.holds else 'NO'} | {f.summary} |")
    lines += ["", "## Raw observations", "", "```json",
              json.dumps({f.probe: f.detail for f in findings}, indent=2, sort_keys=True), "```", ""]
    return "\n".join(lines)


def server_version() -> str:
    with psycopg.connect(settings.ledger1_admin_db_url) as c:
        return str(c.execute("SHOW server_version").fetchone()[0])  # type: ignore[index]


def generated_at() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
