"""Journal partitioning: the measured reasons it is not enabled, and a guard that it stays off."""

from __future__ import annotations

import psycopg
import pytest

from ledgerguard.config import settings
from ledgerguard.db.partition_study import (
    HASH_PARTITIONS,
    compliant_shape_loses_global_uniqueness,
    lines_lookup_fans_out,
    partition_drop_bypasses_immutability,
    unique_needs_partition_key,
)


def test_postgres_refuses_the_real_constraints_on_a_range_partitioned_header() -> None:
    f = unique_needs_partition_key()
    assert f.holds, f.detail
    assert f.detail["attempts"]["primary_key_journal_id"] == "REFUSED 0A000"
    assert f.detail["attempts"]["unique_sequence_number"] == "REFUSED 0A000"
    assert f.detail["attempts"]["lines_fk_to_journal_id"] == "REFUSED 42830"


def test_the_accepted_shape_gives_up_global_uniqueness_of_journal_id_and_sequence() -> None:
    f = compliant_shape_loses_global_uniqueness()
    assert f.holds, f.detail
    r = f.detail["results"]
    assert r["plain.duplicate_journal_id"] == r["plain.duplicate_sequence_number"] == "REJECTED 23505"
    assert r["part.duplicate_journal_id"] == r["part.duplicate_sequence_number"] == "ACCEPTED"


def test_hash_partitioned_lines_fan_out_on_the_journal_id_lookup() -> None:
    f = lines_lookup_fans_out()
    assert f.holds, f.detail
    touched = f.detail["relations_touched"]
    assert touched["by_journal_id"] == {"unpartitioned": 1, "partitioned": HASH_PARTITIONS}
    assert touched["by_account_id"]["partitioned"] == 1


def test_dropping_or_detaching_a_partition_bypasses_the_immutability_triggers() -> None:
    f = partition_drop_bypasses_immutability()
    assert f.holds, f.detail
    assert f.detail["outcome"]["delete_row"].startswith("BLOCKED")
    assert f.detail["outcome"]["truncate"].startswith("BLOCKED")
    assert f.detail["outcome"]["drop_partition"] == "ALLOWED"


@pytest.mark.parametrize("url", [settings.ledger1_admin_db_url, settings.ledger2_admin_db_url])
def test_real_journal_tables_stay_unpartitioned_with_global_unique_constraints(url: str) -> None:
    """If someone partitions the journals, this fails until the study's findings are answered."""
    with psycopg.connect(url) as c:
        kinds = dict(c.execute(
            "SELECT relname, relkind FROM pg_class WHERE relname IN ('journal_headers','journal_lines') "
            "AND relnamespace = 'public'::regnamespace").fetchall())
        assert kinds == {"journal_headers": "r", "journal_lines": "r"}, kinds
        unique_cols = {
            tuple(r[0]) for r in c.execute(
                "SELECT array_agg(a.attname ORDER BY a.attnum) FROM pg_constraint k "
                "JOIN pg_attribute a ON a.attrelid = k.conrelid AND a.attnum = ANY (k.conkey) "
                "WHERE k.conrelid = 'journal_headers'::regclass AND k.contype IN ('p','u') "
                "GROUP BY k.oid").fetchall()}
        assert ("journal_id",) in unique_cols and ("sequence_number",) in unique_cols, unique_cols
