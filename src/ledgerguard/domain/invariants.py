"""Machine-readable catalogue of LedgerGuard V2 system invariants."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InvariantSpec:
    """Stable specification for a LedgerGuard system invariant."""

    id: str
    name: str
    description: str
    category: str


INVARIANT_CATALOGUE: tuple[InvariantSpec, ...] = (
    InvariantSpec(
        id="I1",
        name="balanced_journal",
        description="Every posted journal transaction balances exactly: sum(debits) == sum(credits).",
        category="accounting",
    ),
    InvariantSpec(
        id="I2",
        name="integer_paise_only",
        description="Money is represented as integer paise with no floating-point financial arithmetic.",
        category="accounting",
    ),
    InvariantSpec(
        id="I3",
        name="non_negative_available_balance",
        description="Available balance (posted - held) never becomes negative.",
        category="accounting",
    ),
    InvariantSpec(
        id="I4",
        name="idempotency_key_single_effect",
        description="One idempotency key produces at most one financial effect.",
        category="idempotency",
    ),
    InvariantSpec(
        id="I5",
        name="participant_command_single_effect",
        description="One participant command produces at most one participant effect.",
        category="idempotency",
    ),
    InvariantSpec(
        id="I6",
        name="durable_commit_irreversible",
        description="A durable COMMIT decision never changes to CANCEL.",
        category="protocol",
    ),
    InvariantSpec(
        id="I7",
        name="durable_cancel_irreversible",
        description="A durable CANCEL decision never changes to COMMIT.",
        category="protocol",
    ),
    InvariantSpec(
        id="I8",
        name="committed_transfer_eventually_settles",
        description="A committed transfer eventually settles once required components recover.",
        category="liveness",
    ),
    InvariantSpec(
        id="I9",
        name="cancelled_transfer_never_settles",
        description="A cancelled transfer never settles.",
        category="protocol",
    ),
    InvariantSpec(
        id="I10",
        name="tombstone_blocks_delayed_prepare",
        description="A cancellation tombstone prevents delayed prepare from recreating a hold.",
        category="protocol",
    ),
    InvariantSpec(
        id="I11",
        name="journal_immutability",
        description="Posted journal entries cannot be updated or deleted through ordinary roles.",
        category="audit",
    ),
    InvariantSpec(
        id="I12",
        name="compensating_reversals_preserve_history",
        description="Reversal and refund operations create compensating entries and never erase history.",
        category="audit",
    ),
    InvariantSpec(
        id="I13",
        name="zero_sum_clearing_conservation",
        description="Aggregate cross-ledger clearing delta equals zero in a completed, fully reachable, stopped-and-drained audit.",
        category="reconciliation",
    ),
    InvariantSpec(
        id="I14",
        name="incomplete_audit_never_healthy",
        description="An incomplete audit must never report a healthy PASS result.",
        category="reconciliation",
    ),
    InvariantSpec(
        id="I15",
        name="secrets_never_exposed",
        description="Authentication secrets, raw session tokens, and TOTP secrets never appear in APIs, logs, or screenshots.",
        category="security",
    ),
    InvariantSpec(
        id="I16",
        name="reporter_cannot_read_auth_tables",
        description="The reporter role cannot read authentication tables.",
        category="security",
    ),
)

INVARIANTS_BY_ID: dict[str, InvariantSpec] = {inv.id: inv for inv in INVARIANT_CATALOGUE}
