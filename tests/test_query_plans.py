"""Query-plan assertions at realistic volume (see docs/query_plans.md)."""

from __future__ import annotations

from collections.abc import Iterator

import psycopg
import pytest

from ledgerguard.config import settings
from ledgerguard.db.query_plans import (
    CATALOG,
    COORD,
    LEDGER,
    HotQuery,
    PlanResult,
    ScratchVolume,
    check_source_drift,
    explain,
    explain_without_index,
    find_redundant_indexes,
    index_definition,
    used_index_matches_intended,
)


class Study:
    def __init__(self, vol: ScratchVolume) -> None:
        self.vol = vol
        # Plan everything first, before any negative control mutates the scratch copies.
        self.results: dict[str, PlanResult] = {
            q.name: explain(vol, q) for q in CATALOG if q.db == vol.db
        }


@pytest.fixture(scope="module")
def coord() -> Iterator[Study]:
    with ScratchVolume(COORD) as vol:
        yield Study(vol)


@pytest.fixture(scope="module")
def ledger() -> Iterator[Study]:
    with ScratchVolume(LEDGER) as vol:
        yield Study(vol)


def _study(request: pytest.FixtureRequest, db: str) -> Study:
    return request.getfixturevalue("coord" if db == COORD else "ledger")


@pytest.mark.parametrize("query", CATALOG, ids=[q.name for q in CATALOG])
def test_hot_query_uses_its_intended_index_at_volume(query, request: pytest.FixtureRequest) -> None:
    study = _study(request, query.db)
    result = study.results[query.name]
    assert not result.seq_scan_on_relation, f"{query.name}: sequential scan of {query.relation}"
    assert result.index_used is not None, f"{query.name}: no index scan found"
    assert used_index_matches_intended(study.vol, result), (
        f"{query.name}: planner used {result.index_used}, expected the definition of {query.index}"
    )


def test_every_intended_index_exists_in_the_real_schema() -> None:
    for q in CATALOG:
        url = settings.coordinator_admin_db_url if q.db == COORD else settings.ledger1_admin_db_url
        assert index_definition(url, "public", q.index) is not None, f"{q.name}: {q.index} missing"


def test_catalogued_sql_still_exists_in_the_source_tree() -> None:
    stale = [q.name for q in CATALOG if not check_source_drift(q)]
    assert stale == [], f"source changed under the plan catalogue: {stale}"


# Negative controls: each index this study added or kept is load-bearing - without it the same
# query degrades to a sequential scan at this volume. (Proves the assertions can fail.)
@pytest.mark.parametrize("name", [
    "open_transfer_recovery_sweep", "operator_transfer_list", "transfer_by_idempotency_key",
    "outbox_claim", "holds_as_of", "statement_first_page",
])
def test_removing_the_index_degrades_to_a_sequential_scan(name: str, request: pytest.FixtureRequest) -> None:
    query = next(q for q in CATALOG if q.name == name)
    study = _study(request, query.db)
    degraded = explain_without_index(study.vol, query)
    assert degraded.seq_scan_on_relation, f"{name}: expected a Seq Scan without {query.index}"


def test_no_redundant_indexes_in_any_database() -> None:
    for url in (settings.coordinator_admin_db_url, settings.ledger1_admin_db_url,
                settings.ledger2_admin_db_url):
        assert find_redundant_indexes(url) == []


def test_redundant_index_detector_flags_duplicates_and_prefixes() -> None:
    schema = "redundant_probe"
    with psycopg.connect(settings.ledger1_admin_db_url, autocommit=True) as c:
        c.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        c.execute(f"CREATE SCHEMA {schema}")
        try:
            c.execute(f"CREATE TABLE {schema}.t (a int, b int, c int, UNIQUE (a, b))")
            c.execute(f"CREATE INDEX dup ON {schema}.t (a, b)")          # same columns as the unique
            c.execute(f"CREATE INDEX prefix ON {schema}.t (a)")          # prefix of (a, b)
            c.execute(f"CREATE INDEX fine ON {schema}.t (c)")            # independent
            c.execute(f"CREATE INDEX partial ON {schema}.t (a) WHERE c > 0")  # partial: not redundant
            found = {(r[1], r[2]) for r in find_redundant_indexes(settings.ledger1_admin_db_url, schema)}
        finally:
            c.execute(f"DROP SCHEMA {schema} CASCADE")
    assert {name for name, _ in found} == {"dup", "prefix"}


def test_legacy_lookup_of_transfers_by_key_was_a_sequential_scan(coord: Study) -> None:
    """Why the claims table replaced the old lookup: transfers had no index on idempotency_key."""
    legacy = HotQuery(
        "legacy_transfer_by_key", COORD,
        "SELECT transfer_id, state FROM transfers WHERE idempotency_key = %s", ("{key}",),
        "transfers", "n/a", "n/a", "n/a",
    )
    assert explain(coord.vol, legacy).seq_scan_on_relation
