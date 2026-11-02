"""Domain models and enumerations for LedgerGuard double-entry accounting."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from ledgerguard.domain.money import AmountPaise


class AccountType(StrEnum):
    """Ledger account classification."""

    LIABILITY = "LIABILITY"  # Customer wallets (credit-normal)
    ASSET = "ASSET"  # Cash accounts (debit-normal)
    CONTROL = "CONTROL"  # Clearing control accounts (cross-ledger)


class NormalSide(StrEnum):
    """Accounting normal balance side."""

    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class AccountStatus(StrEnum):
    """Lifecycle status of an account."""

    ACTIVE = "ACTIVE"
    FROZEN = "FROZEN"
    CLOSED = "CLOSED"


class PostingSide(StrEnum):
    """Transaction posting entry side."""

    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class OperationType(StrEnum):
    """Business operations with explicit journal templates."""

    FUNDING = "FUNDING"
    CASH_OUT = "CASH_OUT"
    LOCAL_TRANSFER = "LOCAL_TRANSFER"
    SOURCE_SETTLE = "SOURCE_SETTLE"
    DESTINATION_SETTLE = "DESTINATION_SETTLE"
    REVERSAL = "REVERSAL"


class JournalLineInput(BaseModel):
    """Input line for journal posting."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    account_id: UUID
    side: PostingSide
    amount: AmountPaise


class JournalPostRequest(BaseModel):
    """Input request for posting an atomic double-entry journal."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    journal_id: UUID
    operation_type: OperationType
    currency: str = "INR"
    lines: list[JournalLineInput]
    transfer_id: UUID | None = None
    correlation_id: str | None = None
    description: str | None = None


class AccountBalanceView(BaseModel):
    """Authoritative balance snapshot returned for an account."""

    account_id: UUID
    currency: str = "INR"
    posted_balance_minor: int
    held_amount_minor: int
    available_balance_minor: int
    account_sequence: int
    version: int
    status: AccountStatus


class StatementEntry(BaseModel):
    """Single chronological statement entry for an account."""

    journal_id: UUID
    line_no: int
    account_sequence: int
    operation_type: str
    side: PostingSide
    amount_minor: int
    currency: str
    created_at: datetime
    description: str | None = None
    correlation_id: str | None = None
    transfer_id: UUID | None = None
