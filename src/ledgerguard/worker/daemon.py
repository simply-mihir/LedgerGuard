"""Always-on recovery worker: sleeps on LISTEN, wakes on committed outbox work, sweeps on a timer too.

Correctness never depends on the notification: every wake (by NOTIFY or by the poll timer) runs the same
idempotent recovery sweep, which is a cluster-wide singleton (advisory lock) and acts only on transfers
older than ``min_age_seconds`` so it does not race a request still executing inline.
Only classified transient database failures are retried (after a backoff); anything else stops the worker.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from typing import Any

from ledgerguard.db.errors import is_infrastructure_error
from ledgerguard.worker.orchestrator import recover_pending_transfers
from ledgerguard.worker.outbox import OutboxListener

logger = logging.getLogger(__name__)

Sweep = Callable[[], list[dict[str, Any]]]


def run_worker(
    coord_db_url: str,
    ledger_db_urls: dict[str, str],
    stop: threading.Event,
    *,
    poll_interval_s: float = 5.0,
    min_age_seconds: float = 2.0,
    backoff_s: float = 2.0,
    sweep: Sweep | None = None,
) -> int:
    """Run until ``stop`` is set; returns the number of sweeps performed."""
    do_sweep: Sweep = sweep or (
        lambda: recover_pending_transfers(coord_db_url, ledger_db_urls, min_age_seconds=min_age_seconds)
    )
    sweeps = 0
    while not stop.is_set():
        try:
            with OutboxListener(coord_db_url) as listener:
                while not stop.is_set():
                    do_sweep()
                    sweeps += 1
                    # Wake on a committed outbox insert, or after the poll interval as the fallback.
                    # Sliced so a stop request is honoured within a second.
                    waited = 0.0
                    while waited < poll_interval_s and not stop.is_set():
                        if listener.wait(min(1.0, poll_interval_s - waited)):
                            # New work was just committed. Let it age past ``min_age_seconds`` (a request
                            # may still be executing it inline) before sweeping; sweeping now would skip
                            # it and nothing would wake us again until the next poll.
                            stop.wait(min_age_seconds)
                            break
                        waited += 1.0
        except Exception as exc:
            if not is_infrastructure_error(exc):
                raise
            logger.warning("worker: transient database failure (%s); retrying in %.1fs", exc, backoff_s)
            stop.wait(backoff_s)
    return sweeps
