"""Per-participant circuit breaker, admission control, and adaptive backpressure."""

from __future__ import annotations

import random
import threading
import time
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from ledgerguard.db.pool import get_db_connection


class CircuitState(StrEnum):
    """Per-participant circuit breaker states."""

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class BackpressureRejectedError(Exception):
    """Explicit, retryable backpressure rejection (never cancels committed transfers)."""

    def __init__(self, message: str, *, retry_after_seconds: float = 1.0, participant_id: str = "") -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds
        self.participant_id = participant_id


class ResiliencePolicy(BaseModel):
    """Bounded, validated configuration for admission control and circuit breaking."""

    failure_threshold: int = Field(default=3, ge=1, le=50)
    recovery_success_threshold: int = Field(default=2, ge=1, le=20)
    open_cooldown_seconds: float = Field(default=1.0, ge=0.05, le=300.0)
    half_open_probe_limit: int = Field(default=2, ge=1, le=10)
    max_in_flight_per_participant: int = Field(default=32, ge=1, le=500)
    max_outbox_depth: int = Field(default=200, ge=1, le=10_000)
    hot_account_max_in_flight: int = Field(default=8, ge=1, le=100)
    base_backoff_ms: float = Field(default=50.0, ge=1.0, le=5_000.0)
    max_backoff_ms: float = Field(default=2_000.0, ge=10.0, le=60_000.0)


class ParticipantResilienceController:
    """Thread-safe, DB-backed per-participant circuit breaker and admission controller."""

    def __init__(self, coord_db_url: str, policy: ResiliencePolicy | None = None) -> None:
        self.coord_db_url = coord_db_url
        self.policy = policy or ResiliencePolicy()
        self._lock = threading.Lock()
        self._account_in_flight: dict[str, int] = {}

    def compute_backoff_seconds(self, attempt: int, *, seed: int | None = None) -> float:
        """Compute bounded exponential backoff with jitter."""
        rng = random.Random(seed) if seed is not None else random
        exp_ms = min(self.policy.max_backoff_ms, self.policy.base_backoff_ms * (2 ** max(0, attempt - 1)))
        jittered_ms = rng.uniform(exp_ms * 0.5, exp_ms)
        return round(jittered_ms / 1000.0, 4)

    def admit_new_transfer(self, participant_id: str, *, source_account_id: str | None = None) -> None:
        """Check circuit state, in-flight limit, outbox depth, and hot-account limit for NEW transfers.

        Note: Forward recovery of already-committed transfers bypasses admission control so
        durable obligations always remain recoverable.
        """
        with self._lock:
            if source_account_id and self._account_in_flight.get(source_account_id, 0) >= self.policy.hot_account_max_in_flight:
                raise BackpressureRejectedError(
                    f"Hot-account rate limit reached for {source_account_id}.",
                    retry_after_seconds=0.5,
                    participant_id=participant_id,
                )

            with get_db_connection(self.coord_db_url) as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        "SELECT * FROM participant_resilience_state WHERE participant_id = %s FOR UPDATE;",
                        (participant_id,),
                    )
                    row = cur.fetchone()
                    if not row:
                        cur.execute(
                            "INSERT INTO participant_resilience_state (participant_id) VALUES (%s) RETURNING *;",
                            (participant_id,),
                        )
                        row = cur.fetchone()
                    assert row is not None

                    state = CircuitState(str(row["circuit_state"]))
                    now = datetime.now(UTC)
                    if state == CircuitState.OPEN:
                        next_probe = row["next_probe_at"]
                        if next_probe and now >= next_probe.astimezone(UTC):
                            cur.execute(
                                """
                                UPDATE participant_resilience_state
                                SET circuit_state = 'HALF_OPEN', half_open_probes = 1, success_count = 0,
                                    reason = 'Cooldown elapsed; probing participant', updated_at = NOW()
                                WHERE participant_id = %s;
                                """,
                                (participant_id,),
                            )
                            cur.execute(
                                """
                                INSERT INTO resilience_audit_events (participant_id, from_state, to_state, reason)
                                VALUES (%s, 'OPEN', 'HALF_OPEN', 'Cooldown elapsed; probing participant');
                                """,
                                (participant_id,),
                            )
                            conn.commit()
                        else:
                            conn.commit()
                            raise BackpressureRejectedError(
                                f"Circuit OPEN for {participant_id}: {row['reason']}",
                                retry_after_seconds=self.policy.open_cooldown_seconds,
                                participant_id=participant_id,
                            )
                    elif state == CircuitState.HALF_OPEN:
                        if int(row["half_open_probes"]) >= self.policy.half_open_probe_limit:
                            conn.commit()
                            raise BackpressureRejectedError(
                                f"Circuit HALF_OPEN probe limit reached for {participant_id}.",
                                retry_after_seconds=0.5,
                                participant_id=participant_id,
                            )
                        cur.execute(
                            "UPDATE participant_resilience_state SET half_open_probes = half_open_probes + 1, updated_at = NOW() WHERE participant_id = %s;",
                            (participant_id,),
                        )
                        conn.commit()
                    else:
                        if int(row["in_flight_count"]) >= self.policy.max_in_flight_per_participant:
                            conn.commit()
                            raise BackpressureRejectedError(
                                f"Admission limit reached for {participant_id}.",
                                retry_after_seconds=0.5,
                                participant_id=participant_id,
                            )
                        if int(row["outbox_depth"]) >= self.policy.max_outbox_depth:
                            conn.commit()
                            raise BackpressureRejectedError(
                                f"Outbox backlog limit reached for {participant_id}.",
                                retry_after_seconds=1.0,
                                participant_id=participant_id,
                            )
                        cur.execute(
                            "UPDATE participant_resilience_state SET in_flight_count = in_flight_count + 1, updated_at = NOW() WHERE participant_id = %s;",
                            (participant_id,),
                        )
                        conn.commit()

            if source_account_id:
                self._account_in_flight[source_account_id] = self._account_in_flight.get(source_account_id, 0) + 1

    def release_slot(self, participant_id: str, *, source_account_id: str | None = None) -> None:
        """Release an in-flight admission slot."""
        with self._lock:
            if source_account_id and self._account_in_flight.get(source_account_id, 0) > 0:
                self._account_in_flight[source_account_id] -= 1
            with get_db_connection(self.coord_db_url) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE participant_resilience_state SET in_flight_count = GREATEST(0, in_flight_count - 1), updated_at = NOW() WHERE participant_id = %s;",
                        (participant_id,),
                    )
                conn.commit()

    def record_success(self, participant_id: str, latency_ms: float = 0.0) -> CircuitState:
        """Record a successful participant operation and close HALF_OPEN circuit after hysteresis."""
        with self._lock:
            with get_db_connection(self.coord_db_url) as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        "SELECT * FROM participant_resilience_state WHERE participant_id = %s FOR UPDATE;",
                        (participant_id,),
                    )
                    row = cur.fetchone()
                    if not row:
                        conn.commit()
                        return CircuitState.CLOSED
                    cur_state = CircuitState(str(row["circuit_state"]))
                    new_state = cur_state
                    if cur_state == CircuitState.HALF_OPEN:
                        succ = int(row["success_count"]) + 1
                        if succ >= self.policy.recovery_success_threshold:
                            new_state = CircuitState.CLOSED
                            cur.execute(
                                """
                                UPDATE participant_resilience_state
                                SET circuit_state = 'CLOSED', failure_count = 0, success_count = 0,
                                    half_open_probes = 0, next_probe_at = NULL, p95_latency_ms = %s,
                                    reason = 'Recovered after half-open probes', updated_at = NOW()
                                WHERE participant_id = %s;
                                """,
                                (latency_ms, participant_id),
                            )
                            cur.execute(
                                """
                                INSERT INTO resilience_audit_events (participant_id, from_state, to_state, reason)
                                VALUES (%s, 'HALF_OPEN', 'CLOSED', 'Recovered after half-open probes');
                                """,
                                (participant_id,),
                            )
                        else:
                            cur.execute(
                                "UPDATE participant_resilience_state SET success_count = %s, p95_latency_ms = %s, updated_at = NOW() WHERE participant_id = %s;",
                                (succ, latency_ms, participant_id),
                            )
                    else:
                        cur.execute(
                            "UPDATE participant_resilience_state SET failure_count = 0, p95_latency_ms = %s, updated_at = NOW() WHERE participant_id = %s;",
                            (latency_ms, participant_id),
                        )
                conn.commit()
            return new_state

    def record_failure(self, participant_id: str, reason: str = "participant_failure") -> CircuitState:
        """Record a participant failure and open circuit when threshold is reached."""
        with self._lock:
            with get_db_connection(self.coord_db_url) as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        "SELECT * FROM participant_resilience_state WHERE participant_id = %s FOR UPDATE;",
                        (participant_id,),
                    )
                    row = cur.fetchone()
                    assert row is not None
                    cur_state = CircuitState(str(row["circuit_state"]))
                    fails = int(row["failure_count"]) + 1
                    next_probe = datetime.now(UTC) + timedelta(seconds=self.policy.open_cooldown_seconds)
                    if cur_state == CircuitState.HALF_OPEN or fails >= self.policy.failure_threshold:
                        cur.execute(
                            """
                            UPDATE participant_resilience_state
                            SET circuit_state = 'OPEN', failure_count = %s, success_count = 0,
                                half_open_probes = 0, last_failure_at = NOW(), next_probe_at = %s,
                                reason = %s, updated_at = NOW()
                            WHERE participant_id = %s;
                            """,
                            (fails, next_probe, reason, participant_id),
                        )
                        if cur_state != CircuitState.OPEN:
                            cur.execute(
                                """
                                INSERT INTO resilience_audit_events (participant_id, from_state, to_state, reason)
                                VALUES (%s, %s, 'OPEN', %s);
                                """,
                                (participant_id, cur_state.value, reason),
                            )
                        conn.commit()
                        return CircuitState.OPEN
                    cur.execute(
                        """
                        UPDATE participant_resilience_state
                        SET failure_count = %s, last_failure_at = NOW(), reason = %s, updated_at = NOW()
                        WHERE participant_id = %s;
                        """,
                        (fails, reason, participant_id),
                    )
                conn.commit()
            return cur_state

    def get_health_snapshot(self) -> list[dict[str, Any]]:
        """Return live per-participant circuit & backpressure telemetry."""
        with get_db_connection(self.coord_db_url) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT * FROM participant_resilience_state ORDER BY participant_id ASC;")
                rows = [dict(r) for r in cur.fetchall()]
                cur.execute(
                    """
                    SELECT COUNT(*) AS cnt,
                           COALESCE(EXTRACT(EPOCH FROM (NOW() - MIN(created_at))), 0) AS oldest_age
                    FROM outbox_events
                    WHERE delivered_at IS NULL;
                    """
                )
                ob = cur.fetchone() or {"cnt": 0, "oldest_age": 0.0}
        for r in rows:
            r["outbox_depth"] = int(ob["cnt"])
            r["oldest_pending_age_seconds"] = round(float(ob["oldest_age"]), 2)
            r["operator_explanation"] = (
                f"Circuit {r['circuit_state']} ({r['reason']}). Committed transfers remain forward-recoverable."
            )
        return rows


def sleep_with_backoff(controller: ParticipantResilienceController, attempt: int) -> float:
    """Sleep for jittered exponential backoff and return duration."""
    delay = controller.compute_backoff_seconds(attempt)
    time.sleep(delay)
    return delay
