"""Deterministic failpoints for simulating network, crash, and transport failures across 2PC."""

from __future__ import annotations

import threading
from uuid import UUID


class FailpointError(Exception):
    """Base class for injected failpoint errors."""


class TransportTimeoutError(FailpointError):
    """Simulates a network timeout or dropped reply."""


class CrashAfterCommitError(FailpointError):
    """Simulates coordinator process crash immediately after durable COMMIT decision."""


class CrashAfterSourceConfirmError(FailpointError):
    """Simulates coordinator crash after source confirmation succeeds but before destination confirmation."""


class FailpointManager:
    """Thread-safe manager for deterministic failure injection."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active_failpoints: dict[str, set[UUID] | bool] = {}

    def set_failpoint(self, name: str, transfer_id: UUID | None = None) -> None:
        """Activate a failpoint either globally or for a specific transfer."""
        with self._lock:
            if transfer_id is None:
                self._active_failpoints[name] = True
            else:
                existing = self._active_failpoints.get(name)
                if isinstance(existing, set):
                    existing.add(transfer_id)
                else:
                    self._active_failpoints[name] = {transfer_id}

    def clear(self) -> None:
        """Clear all active failpoints."""
        with self._lock:
            self._active_failpoints.clear()

    def check(self, name: str, transfer_id: UUID | None = None) -> None:
        """Check if a failpoint should trigger, raising the corresponding error."""
        with self._lock:
            active = self._active_failpoints.get(name)
            if not active:
                return

            triggered = False
            if isinstance(active, bool) and active:
                triggered = True
                # Consume one-shot global failpoint
                self._active_failpoints.pop(name, None)
            elif isinstance(active, set) and transfer_id and transfer_id in active:
                triggered = True
                active.remove(transfer_id)
                if not active:
                    self._active_failpoints.pop(name, None)

        if triggered:
            if name == "FAIL_AFTER_SOURCE_PREPARE_REPLY":
                raise TransportTimeoutError("Simulated lost reply after source prepare committed.")
            elif name == "FAIL_AFTER_COMMIT_BEFORE_SOURCE_CONFIRM":
                raise CrashAfterCommitError("Simulated coordinator crash immediately after durable COMMIT.")
            elif name == "FAIL_AFTER_SOURCE_CONFIRM_BEFORE_DEST_CONFIRM":
                raise CrashAfterSourceConfirmError(
                    "Simulated crash after source confirm settled, before destination confirm."
                )
            elif name == "FAIL_AFTER_DEST_CONFIRM_REPLY":
                raise TransportTimeoutError("Simulated lost reply after destination confirm committed.")
            else:
                raise FailpointError(f"Simulated fault triggered: {name}")


failpoints = FailpointManager()
