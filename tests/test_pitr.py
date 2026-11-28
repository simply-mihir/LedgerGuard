"""Point-in-time recovery: WAL archive + base backup undo a destructive operator error."""

from __future__ import annotations

import pytest

from ledgerguard.db.pool import close_all_pools
from ledgerguard.dr.pitr import docker_available, run_pitr_drill

pytestmark = pytest.mark.skipif(not docker_available(), reason="docker or postgres:17-alpine not available")


def test_recovery_to_a_named_restore_point_undoes_a_dropped_table() -> None:
    try:
        r = run_pitr_drill()
    finally:
        close_all_pools()
    assert r.journals_before_disaster >= 5
    assert r.disaster_destroyed_primary_table, "the drill must really destroy the primary's journal_lines"
    assert r.restored_has_post_backup_postings, "postings made after the base backup come back from archived WAL"
    assert r.restored_journals == r.journals_before_disaster
    assert r.restored_excludes_post_disaster_write, "recovery stops at the restore point, not at end of WAL"
    assert r.restored_chain_ok, "the restored journal hash chain must verify end to end"
    assert r.wal_segments_archived >= 1
