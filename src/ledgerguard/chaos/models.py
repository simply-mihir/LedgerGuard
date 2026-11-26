"""Data models and fault definitions for LedgerGuard Chaos Campaigns."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ChaosFaultType(StrEnum):
    """All 18 supported deterministic chaos fault modes."""

    COORDINATOR_CRASH_BEFORE_SOURCE_PREPARE = "COORDINATOR_CRASH_BEFORE_SOURCE_PREPARE"
    COORDINATOR_CRASH_AFTER_SOURCE_PREPARE = "COORDINATOR_CRASH_AFTER_SOURCE_PREPARE"
    COORDINATOR_CRASH_AFTER_DEST_PREPARE = "COORDINATOR_CRASH_AFTER_DEST_PREPARE"
    COORDINATOR_CRASH_AFTER_COMMIT = "COORDINATOR_CRASH_AFTER_COMMIT"
    COORDINATOR_CRASH_BETWEEN_CONFIRMS = "COORDINATOR_CRASH_BETWEEN_CONFIRMS"
    SOURCE_PARTICIPANT_UNAVAILABLE = "SOURCE_PARTICIPANT_UNAVAILABLE"
    DEST_PARTICIPANT_UNAVAILABLE = "DEST_PARTICIPANT_UNAVAILABLE"
    OUTBOX_WORKER_CRASH = "OUTBOX_WORKER_CRASH"
    RECOVERY_WORKER_CRASH = "RECOVERY_WORKER_CRASH"
    DUPLICATE_COMMAND_DELIVERY = "DUPLICATE_COMMAND_DELIVERY"
    REORDERED_COMMAND_DELIVERY = "REORDERED_COMMAND_DELIVERY"
    LOST_REPLY_AFTER_PARTICIPANT_COMMIT = "LOST_REPLY_AFTER_PARTICIPANT_COMMIT"
    TEMP_DB_CONNECTION_FAILURE = "TEMP_DB_CONNECTION_FAILURE"
    POSTGRES_PARTICIPANT_RESTART = "POSTGRES_PARTICIPANT_RESTART"
    CLIENT_RETRY_STORM = "CLIENT_RETRY_STORM"
    HOT_ACCOUNT_CONTENTION = "HOT_ACCOUNT_CONTENTION"
    ARTIFICIAL_PROCESSING_DELAY = "ARTIFICIAL_PROCESSING_DELAY"
    EXHAUSTED_RETRY_BUDGET = "EXHAUSTED_RETRY_BUDGET"


class ChaosCampaignConfig(BaseModel):
    """Configuration for a deterministic chaos campaign."""

    seed: int = 42
    operation_count: int = Field(default=24, ge=1, le=5000)
    num_accounts: int = Field(default=6, ge=4, le=100)
    initial_balance_minor: int = Field(default=100_000, ge=1_000)
    worker_count: int = Field(default=4, ge=1, le=32)
    min_amount_minor: int = Field(default=100, ge=1)
    max_amount_minor: int = Field(default=2_500, ge=1)
    local_ratio: float = Field(default=0.35, ge=0.0, le=1.0)
    hot_account_percentage: float = Field(default=0.25, ge=0.0, le=1.0)
    duplicate_probability: float = Field(default=0.15, ge=0.0, le=1.0)
    delay_probability: float = Field(default=0.10, ge=0.0, le=1.0)
    reorder_probability: float = Field(default=0.10, ge=0.0, le=1.0)
    failure_schedule: list[ChaosFaultType] = Field(
        default_factory=lambda: [
            ChaosFaultType.COORDINATOR_CRASH_AFTER_COMMIT,
            ChaosFaultType.COORDINATOR_CRASH_BETWEEN_CONFIRMS,
            ChaosFaultType.LOST_REPLY_AFTER_PARTICIPANT_COMMIT,
            ChaosFaultType.DUPLICATE_COMMAND_DELIVERY,
            ChaosFaultType.REORDERED_COMMAND_DELIVERY,
            ChaosFaultType.CLIENT_RETRY_STORM,
            ChaosFaultType.HOT_ACCOUNT_CONTENTION,
            ChaosFaultType.ARTIFICIAL_PROCESSING_DELAY,
        ]
    )
    recovery_timeout_seconds: float = Field(default=10.0, ge=0.5, le=120.0)
    invariant_check_interval: int = Field(default=8, ge=1, le=500)


class FaultTimelineEntry(BaseModel):
    """Single fault injection event recorded during a campaign."""

    step: int
    fault_type: str
    target: str
    injected_at: str
    restored_at: str | None = None
    recovered: bool = True
    details: str = ""


class InvariantResult(BaseModel):
    """Verification outcome for one invariant ID."""

    id: str
    name: str
    status: str  # PASS, FAIL, INCOMPLETE
    details: str = ""


class ChaosCampaignReport(BaseModel):
    """Complete structured output of a chaos campaign."""

    campaign_id: str
    seed: int
    git_sha: str
    environment: dict[str, Any] = Field(default_factory=dict)
    config: ChaosCampaignConfig
    status: str  # PASS, FAIL, INCOMPLETE
    operations_attempted: int
    settled_count: int
    cancelled_count: int
    recovered_count: int
    duplicate_messages_ignored: int
    fault_counts: dict[str, int] = Field(default_factory=dict)
    max_unresolved_duration_ms: float = 0.0
    recovery_latency_ms: dict[str, float] = Field(default_factory=dict)
    invariant_results: list[InvariantResult] = Field(default_factory=list)
    reconciliation_result: dict[str, Any] = Field(default_factory=dict)
    fault_timeline: list[FaultTimelineEntry] = Field(default_factory=list)
    counterexample_history: dict[str, Any] | None = None
