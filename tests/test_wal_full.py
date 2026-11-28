"""WAL volume exhaustion: clients get a classified infrastructure failure, never a business rejection."""

from __future__ import annotations

import pytest

from ledgerguard.faults.disk_full import docker_available
from ledgerguard.faults.wal_full import run_wal_full_drill

pytestmark = pytest.mark.skipif(not docker_available(), reason="docker or postgres:17-alpine not available")


def test_a_full_wal_volume_fails_writes_as_a_classified_infrastructure_error() -> None:
    r = run_wal_full_drill()
    assert r.batches_before_failure > 0, "writes succeeded until the volume filled"
    assert r.error_sqlstate in {"53100", "58030"} or r.error_sqlstate is None, r  # disk full / io / dropped
    assert r.error_is_infrastructure, "the failure must classify as infrastructure (503), not a business error"
    assert r.server_stopped and r.log_mentions_wal, "the server stops because it cannot write WAL, and says so"
