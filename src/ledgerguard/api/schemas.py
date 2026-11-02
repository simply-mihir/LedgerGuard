"""Pydantic schemas for the LedgerGuard public REST API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from ledgerguard.domain.models import AccountStatus, PostingSide


class CreateCustomerRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    email: str = Field(..., min_length=3, max_length=255)


class CustomerResponse(BaseModel):
    customer_id: UUID
    name: str
    email: str
    status: str
    created_at: datetime


class CreateAccountRequest(BaseModel):
    customer_id: UUID | None = None
    currency: str = Field(default="INR", max_length=3)
    name: str | None = None


class AccountResponse(BaseModel):
    account_id: UUID
    currency: str
    posted_balance_minor: int
    held_amount_minor: int
    available_balance_minor: int
    account_sequence: int
    version: int
    status: AccountStatus


class StatementEntryResponse(BaseModel):
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


class StatementResponse(BaseModel):
    account_id: UUID
    entries: list[StatementEntryResponse]
    next_cursor: int | None = None


class FundingRequest(BaseModel):
    account_id: UUID
    amount_minor: int = Field(..., gt=0, le=100_000_000_000)
    correlation_id: str | None = None
    description: str | None = None


class CashOutRequest(BaseModel):
    account_id: UUID
    amount_minor: int = Field(..., gt=0, le=100_000_000_000)
    correlation_id: str | None = None
    description: str | None = None


class TransferRequest(BaseModel):
    source_account_id: UUID
    destination_account_id: UUID
    amount_minor: int = Field(..., gt=0, le=100_000_000_000)
    currency: str = Field(default="INR", max_length=3)
    correlation_id: str | None = None
    description: str | None = None


class TransferResponse(BaseModel):
    transfer_id: UUID
    status: str
    source_account_id: UUID
    destination_account_id: UUID
    amount_minor: int
    currency: str
    journal_id: UUID | None = None
    created_at: datetime | None = None
    is_reversed: bool = False
    reversal_id: UUID | None = None
    attention_required: bool = False
    attention_reason: str | None = None


class ReversalRequest(BaseModel):
    reason: str | None = None


class ReversalResponse(BaseModel):
    reversal_id: UUID
    original_transfer_id: UUID
    reversal_transfer_id: UUID
    status: str
    amount_minor: int
    currency: str


class StatusChangeRequest(BaseModel):
    reason: str | None = None


class ReconciliationFindingResponse(BaseModel):
    check_name: str
    severity: str
    resource_id: str
    details: str


class ReconciliationRunResponse(BaseModel):
    run_id: str
    run_at: datetime
    status: str
    accounts_examined: int
    journals_examined: int
    lines_examined: int
    trial_balance_debit: int
    trial_balance_credit: int
    findings: list[ReconciliationFindingResponse]


class SystemOverviewResponse(BaseModel):
    reachability: dict[str, bool]
    total_accounts: int
    total_customers: int
    total_transfers: int
    settled_transfers: int
    pending_transfers: int
    oldest_pending_age_seconds: int
    clearing_sum: int
    last_reconciliation_status: str
    fault_injection_enabled: bool


class DirectoryAccountResponse(BaseModel):
    account_id: UUID
    customer_id: UUID
    ledger_id: str
    routing_version: int
    provisioning_state: str
    currency: str
    posted_balance_minor: int
    held_amount_minor: int
    available_balance_minor: int
    status: str


class WorkflowTimelineEntryResponse(BaseModel):
    event_id: UUID
    transfer_id: UUID
    event_type: str
    details: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    created_at: datetime


class ExperimentRunRequest(BaseModel):
    scenario: str  # "SIGNATURE_RECOVERY", "LOST_PREPARE_REPLY", "DESTINATION_FROZEN"


class ExperimentStepResponse(BaseModel):
    step_number: int
    phase: str
    action: str
    outcome: str
    details: str


class ExperimentRunResponse(BaseModel):
    scenario: str
    transfer_id: UUID
    status: str
    steps: list[ExperimentStepResponse]
    final_accounting_state: dict[str, int | str]
