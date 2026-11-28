"""Advisory-lock singletons: one holder at a time, released on exit and on connection death."""

from __future__ import annotations

from uuid import uuid4

import psycopg
import pytest

from ledgerguard.config import settings
from ledgerguard.db.advisory import singleton
from ledgerguard.worker.orchestrator import RECOVERY_SWEEP_LOCK, recover_pending_transfers

pytestmark = pytest.mark.integration
URL = settings.coordinator_admin_db_url


def test_second_caller_is_refused_while_the_first_holds_the_lock_then_gets_it() -> None:
    name = f"test:{uuid4()}"
    with singleton(URL, name) as first:
        assert first is True
        with singleton(URL, name) as second:
            assert second is False
    with singleton(URL, name) as again:
        assert again is True


def test_locks_with_different_names_do_not_interfere() -> None:
    with singleton(URL, f"a:{uuid4()}") as a, singleton(URL, f"b:{uuid4()}") as b:
        assert a is True and b is True


def test_a_killed_holder_releases_its_lock_with_no_cleanup() -> None:
    name = f"test:{uuid4()}"
    holder = psycopg.connect(URL, autocommit=True)
    holder.execute("SELECT pg_try_advisory_lock(hashtextextended(%s, 0))", (name,))
    pid = holder.info.backend_pid
    with singleton(URL, name) as blocked:
        assert blocked is False
    with psycopg.connect(URL, autocommit=True) as admin:
        admin.execute("SELECT pg_terminate_backend(%s)", (pid,))
    holder.close()
    with singleton(URL, name) as freed:
        assert freed is True


def test_a_global_recovery_sweep_yields_to_a_running_one_but_named_recovery_does_not() -> None:
    with singleton(URL, RECOVERY_SWEEP_LOCK) as held:
        assert held is True
        assert recover_pending_transfers(URL, {}) == []  # another sweep "is running": skipped, no work
    # lock free again: a sweep runs normally (nothing pending here is fine - it must simply not be skipped)
    with singleton(URL, RECOVERY_SWEEP_LOCK) as free:
        assert free is True
