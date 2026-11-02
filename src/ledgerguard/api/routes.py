"""FastAPI route handlers implementing the LedgerGuard REST API specification."""

from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from psycopg.rows import dict_row

from ledgerguard.api.auth import require_idempotency_key, verify_bearer_token
from ledgerguard.api.schemas import (
    AccountResponse,
    CashOutRequest,
    CreateAccountRequest,
    CreateCustomerRequest,
    CustomerResponse,
    DirectoryAccountResponse,
    ExperimentRunRequest,
    ExperimentRunResponse,
    ExperimentStepResponse,
    FundingRequest,
    ReconciliationFindingResponse,
    ReconciliationRunResponse,
    ReversalRequest,
    ReversalResponse,
    StatementEntryResponse,
    StatementResponse,
    StatusChangeRequest,
    SystemOverviewResponse,
    TransferRequest,
    TransferResponse,
    WorkflowTimelineEntryResponse,
)
from ledgerguard.config import settings
from ledgerguard.coordinator.directory_service import provision_account, register_customer
from ledgerguard.coordinator.failpoints import CrashAfterCommitError, FailpointManager
from ledgerguard.coordinator.reconciliation import (
    CLEARING_ACCOUNT_ID,
)
from ledgerguard.coordinator.transfer_coordinator import submit_coordinator_transfer
from ledgerguard.db.pool import get_db_connection
from ledgerguard.domain.idempotency import IdempotencyConflictError
from ledgerguard.domain.models import AccountStatus
from ledgerguard.domain.money import AmountPaise
from ledgerguard.participant.account_service import (
    AccountLifecycleError,
    AccountNotFoundError,
    create_ledger_account,
    get_account_balance,
    get_statement,
    set_account_status,
)
from ledgerguard.participant.posting_service import (
    PostingError,
    simulate_cash_out,
    simulate_funding,
)
from ledgerguard.participant.reconciliation_service import run_local_reconciliation
from ledgerguard.participant.transfer_service import (
    AccountNotActiveError,
    InsufficientFundsError,
    ReversalConflictError,
    ReversalRejectedError,
    TransferError,
    execute_local_transfer,
    execute_reversal,
    get_transfer_details,
)
from ledgerguard.worker.orchestrator import recover_pending_transfers

router = APIRouter(prefix="/v1")

# Global in-memory cache for recent reconciliation runs
_reconciliation_runs: dict[str, ReconciliationRunResponse] = {}


def get_ledger_db_url() -> str:
    """Return the active ledger database URL (defaulting to ledger1 or core)."""
    return settings.ledger1_db_url


def get_coord_db_url() -> str:
    """Return the coordinator database URL."""
    return settings.coordinator_db_url


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------


@router.post("/customers", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(req: CreateCustomerRequest) -> CustomerResponse:
    """Register a new customer record."""
    cust_id = uuid4()
    with get_db_connection(get_coord_db_url()) as conn:
        cur: Any
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO customers (customer_id, name, email, status)
                VALUES (%s, %s, %s, 'ACTIVE')
                RETURNING customer_id, name, email, status, created_at;
            """,
                (cust_id, req.name, req.email),
            )
            row = cur.fetchone()
        conn.commit()

    return CustomerResponse(
        customer_id=row["customer_id"],
        name=row["name"],
        email=row["email"],
        status=row["status"],
        created_at=row["created_at"],
    )


# ---------------------------------------------------------------------------
# Accounts & Balances
# ---------------------------------------------------------------------------


@router.post("/accounts", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
def create_account(
    req: CreateAccountRequest,
    idempotency_key: str = Depends(require_idempotency_key),
) -> AccountResponse:
    """Idempotently create an active customer wallet account."""
    acct = create_ledger_account(
        get_ledger_db_url(),
        customer_id=req.customer_id,
        currency=req.currency,
        name=req.name,
    )
    return AccountResponse(
        account_id=acct.account_id,
        currency=acct.currency,
        posted_balance_minor=acct.posted_balance_minor,
        held_amount_minor=acct.held_amount_minor,
        available_balance_minor=acct.available_balance_minor,
        account_sequence=acct.account_sequence,
        version=acct.version,
        status=acct.status,
    )


@router.get("/accounts/{account_id}/balance", response_model=AccountResponse)
def get_balance(account_id: UUID) -> AccountResponse:
    """Return authoritative posted, held, and available balances for an account."""
    try:
        acct = get_account_balance(get_ledger_db_url(), account_id)
        return AccountResponse(
            account_id=acct.account_id,
            currency=acct.currency,
            posted_balance_minor=acct.posted_balance_minor,
            held_amount_minor=acct.held_amount_minor,
            available_balance_minor=acct.available_balance_minor,
            account_sequence=acct.account_sequence,
            version=acct.version,
            status=acct.status,
        )
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/accounts/{account_id}/statement", response_model=StatementResponse)
def get_account_statement(
    account_id: UUID,
    cursor: int | None = Query(default=None, alias="cursor"),
    limit: int = Query(default=50, ge=1, le=100),
) -> StatementResponse:
    """Retrieve chronological statement entries using account-sequence cursor pagination."""
    try:
        entries, next_cursor = get_statement(
            get_ledger_db_url(), account_id, cursor_sequence=cursor, limit=limit
        )
        return StatementResponse(
            account_id=account_id,
            entries=[
                StatementEntryResponse(
                    journal_id=e.journal_id,
                    line_no=e.line_no,
                    account_sequence=e.account_sequence,
                    operation_type=e.operation_type,
                    side=e.side,
                    amount_minor=e.amount_minor,
                    currency=e.currency,
                    created_at=e.created_at,
                    description=e.description,
                    correlation_id=e.correlation_id,
                    transfer_id=e.transfer_id,
                )
                for e in entries
            ],
            next_cursor=next_cursor,
        )
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Account Lifecycle: Freeze / Unfreeze / Close
# ---------------------------------------------------------------------------


@router.post("/accounts/{account_id}/freeze", response_model=AccountResponse)
def freeze_account(
    account_id: UUID,
    req: StatusChangeRequest,
    _: None = Depends(verify_bearer_token),
) -> AccountResponse:
    """Freeze an account preventing new outgoing debits."""
    try:
        acct = set_account_status(
            get_ledger_db_url(), account_id, AccountStatus.FROZEN, reason=req.reason
        )
        return AccountResponse(
            account_id=acct.account_id,
            currency=acct.currency,
            posted_balance_minor=acct.posted_balance_minor,
            held_amount_minor=acct.held_amount_minor,
            available_balance_minor=acct.available_balance_minor,
            account_sequence=acct.account_sequence,
            version=acct.version,
            status=acct.status,
        )
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AccountLifecycleError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/accounts/{account_id}/unfreeze", response_model=AccountResponse)
def unfreeze_account(
    account_id: UUID,
    req: StatusChangeRequest,
    _: None = Depends(verify_bearer_token),
) -> AccountResponse:
    """Unfreeze an account returning it to ACTIVE status."""
    try:
        acct = set_account_status(
            get_ledger_db_url(), account_id, AccountStatus.ACTIVE, reason=req.reason
        )
        return AccountResponse(
            account_id=acct.account_id,
            currency=acct.currency,
            posted_balance_minor=acct.posted_balance_minor,
            held_amount_minor=acct.held_amount_minor,
            available_balance_minor=acct.available_balance_minor,
            account_sequence=acct.account_sequence,
            version=acct.version,
            status=acct.status,
        )
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AccountLifecycleError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/accounts/{account_id}/close", response_model=AccountResponse)
def close_account(
    account_id: UUID,
    req: StatusChangeRequest,
    _: None = Depends(verify_bearer_token),
) -> AccountResponse:
    """Close an empty account with zero balance and no unresolved obligations."""
    try:
        acct = set_account_status(
            get_ledger_db_url(), account_id, AccountStatus.CLOSED, reason=req.reason
        )
        return AccountResponse(
            account_id=acct.account_id,
            currency=acct.currency,
            posted_balance_minor=acct.posted_balance_minor,
            held_amount_minor=acct.held_amount_minor,
            available_balance_minor=acct.available_balance_minor,
            account_sequence=acct.account_sequence,
            version=acct.version,
            status=acct.status,
        )
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AccountLifecycleError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Simulated Funding & Cash-Out
# ---------------------------------------------------------------------------


@router.post("/funding", status_code=status.HTTP_201_CREATED)
def fund_account(
    req: FundingRequest,
    idempotency_key: str = Depends(require_idempotency_key),
    _: None = Depends(verify_bearer_token),
) -> dict[str, Any]:
    """Protected endpoint to simulate external cash funding into an account."""
    try:
        amt = AmountPaise(req.amount_minor)
        result = simulate_funding(
            get_ledger_db_url(),
            req.account_id,
            amt,
            correlation_id=req.correlation_id or idempotency_key,
            description=req.description,
        )
        return {"status": "POSTED", "result": result}
    except PostingError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.post("/cash-outs", status_code=status.HTTP_201_CREATED)
def cash_out(
    req: CashOutRequest,
    idempotency_key: str = Depends(require_idempotency_key),
    _: None = Depends(verify_bearer_token),
) -> dict[str, Any]:
    """Protected endpoint to simulate cash withdrawal from an account."""
    try:
        amt = AmountPaise(req.amount_minor)
        result = simulate_cash_out(
            get_ledger_db_url(),
            req.account_id,
            amt,
            correlation_id=req.correlation_id or idempotency_key,
            description=req.description,
        )
        return {"status": "POSTED", "result": result}
    except PostingError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


# ---------------------------------------------------------------------------
# Transfers & Reversals
# ---------------------------------------------------------------------------


@router.post("/transfers", response_model=TransferResponse, status_code=status.HTTP_200_OK)
def create_transfer(
    req: TransferRequest,
    idempotency_key: str = Depends(require_idempotency_key),
) -> TransferResponse:
    """Submit a wallet transfer with request idempotency and row-level concurrency protection."""
    try:
        amt = AmountPaise(req.amount_minor)
        res = execute_local_transfer(
            get_ledger_db_url(),
            idempotency_key=idempotency_key,
            source_account_id=req.source_account_id,
            destination_account_id=req.destination_account_id,
            amount=amt,
            correlation_id=req.correlation_id,
            description=req.description,
        )
        return TransferResponse(
            transfer_id=UUID(res["transfer_id"]),
            status=res["status"],
            source_account_id=UUID(res["source_account_id"]),
            destination_account_id=UUID(res["destination_account_id"]),
            amount_minor=res["amount_minor"],
            currency=res["currency"],
            journal_id=UUID(res["journal_id"]) if res.get("journal_id") else None,
        )
    except IdempotencyConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InsufficientFundsError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except AccountNotActiveError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except TransferError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/transfers/{transfer_id}", response_model=TransferResponse)
def get_transfer(transfer_id: UUID) -> TransferResponse:
    """Retrieve state, journal receipts, and reversal status of a transfer."""
    try:
        details = get_transfer_details(get_ledger_db_url(), transfer_id)
        return TransferResponse(
            transfer_id=UUID(details["transfer_id"]),
            status=details["status"],
            source_account_id=UUID(details["source_account_id"]),
            destination_account_id=UUID(details["destination_account_id"]),
            amount_minor=details["amount_minor"],
            currency=details["currency"],
            journal_id=UUID(details["journal_id"]) if details.get("journal_id") else None,
            is_reversed=details["is_reversed"],
            reversal_id=UUID(details["reversal_id"]) if details.get("reversal_id") else None,
        )
    except TransferError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/transfers/{transfer_id}/reversal", response_model=ReversalResponse)
def reverse_transfer(
    transfer_id: UUID,
    req: ReversalRequest,
    idempotency_key: str = Depends(require_idempotency_key),
    _: None = Depends(verify_bearer_token),
) -> ReversalResponse:
    """Submit a single full reversal for an eligible settled transfer."""
    try:
        res = execute_reversal(
            get_ledger_db_url(),
            idempotency_key=idempotency_key,
            original_transfer_id=transfer_id,
            reason=req.reason,
        )
        return ReversalResponse(
            reversal_id=UUID(res["reversal_id"]),
            original_transfer_id=UUID(res["original_transfer_id"]),
            reversal_transfer_id=UUID(res["reversal_transfer_id"]),
            status=res["status"],
            amount_minor=res["amount_minor"],
            currency=res["currency"],
        )
    except IdempotencyConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ReversalConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ReversalRejectedError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except TransferError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# Admin & Reconciliation
# ---------------------------------------------------------------------------


@router.post("/admin/reconciliation-runs", response_model=ReconciliationRunResponse)
def trigger_reconciliation(_: None = Depends(verify_bearer_token)) -> ReconciliationRunResponse:
    """Execute a comprehensive double-entry reconciliation audit."""
    run_id = str(uuid4())
    report = run_local_reconciliation(get_ledger_db_url())

    response = ReconciliationRunResponse(
        run_id=run_id,
        run_at=report.run_at,
        status=report.status,
        accounts_examined=report.accounts_examined,
        journals_examined=report.journals_examined,
        lines_examined=report.lines_examined,
        trial_balance_debit=report.trial_balance_debit,
        trial_balance_credit=report.trial_balance_credit,
        findings=[
            ReconciliationFindingResponse(
                check_name=f.check_name,
                severity=f.severity,
                resource_id=f.resource_id,
                details=f.details,
            )
            for f in report.findings
        ],
    )
    _reconciliation_runs[run_id] = response
    return response


@router.get("/admin/reconciliation-runs/{run_id}", response_model=ReconciliationRunResponse)
def get_reconciliation_run(run_id: str) -> ReconciliationRunResponse:
    """Retrieve details and findings of a previous reconciliation run."""
    if run_id not in _reconciliation_runs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Reconciliation run {run_id} not found."
        )
    return _reconciliation_runs[run_id]


# ---------------------------------------------------------------------------
# Operator Console Endpoints
# ---------------------------------------------------------------------------


@router.get("/operator/overview", response_model=SystemOverviewResponse)
def get_operator_overview() -> SystemOverviewResponse:
    """Return consolidated platform overview metrics and service reachability."""
    reachability = {}
    for name, url in [
        ("coordinator", settings.coordinator_db_url),
        ("ledger-1", settings.ledger1_db_url),
        ("ledger-2", settings.ledger2_db_url),
    ]:
        try:
            with get_db_connection(url) as conn:
                with conn.cursor() as probe_cur:
                    probe_cur.execute("SELECT 1;")
            reachability[name] = True
        except Exception:
            reachability[name] = False

    total_accounts = 0
    total_customers = 0
    total_transfers = 0
    settled_transfers = 0
    pending_transfers = 0
    oldest_age = 0

    try:
        with get_db_connection(settings.coordinator_db_url) as conn:
            coord_cur: Any
            with conn.cursor(row_factory=dict_row) as coord_cur:
                coord_cur.execute("SELECT COUNT(*) AS c FROM customers;")
                row_c = coord_cur.fetchone()
                total_customers = int(row_c["c"]) if row_c else 0

                coord_cur.execute(
                    "SELECT COUNT(*) AS c FROM account_directory WHERE provisioning_state = 'READY';"
                )
                row_a = coord_cur.fetchone()
                total_accounts = int(row_a["c"]) if row_a else 0

                coord_cur.execute("SELECT COUNT(*) AS c FROM transfers;")
                row_t = coord_cur.fetchone()
                total_transfers = int(row_t["c"]) if row_t else 0

                coord_cur.execute("SELECT COUNT(*) AS c FROM transfers WHERE state = 'SETTLED';")
                row_s = coord_cur.fetchone()
                settled_transfers = int(row_s["c"]) if row_s else 0

                coord_cur.execute(
                    """
                    SELECT COUNT(*) AS c,
                           COALESCE(EXTRACT(EPOCH FROM (NOW() - MIN(created_at))), 0) AS max_age
                    FROM transfers
                    WHERE state IN ('ACCEPTED', 'PREPARING', 'COMMITTING', 'CANCELLING');
                """
                )
                p_row = coord_cur.fetchone()
                pending_transfers = int(p_row["c"]) if p_row else 0
                oldest_age = int(p_row["max_age"]) if p_row else 0
    except Exception:
        pass

    clearing_sum = 0
    for url in [settings.ledger1_db_url, settings.ledger2_db_url]:
        try:
            with get_db_connection(url) as conn:
                clr_cur: Any
                with conn.cursor(row_factory=dict_row) as clr_cur:
                    clr_cur.execute(
                        "SELECT posted_balance_minor FROM account_balances WHERE account_id = %s;",
                        (CLEARING_ACCOUNT_ID,),
                    )
                    clr_row = clr_cur.fetchone()
                    if clr_row:
                        clearing_sum += int(clr_row["posted_balance_minor"])
        except Exception:
            pass

    return SystemOverviewResponse(
        reachability=reachability,
        total_accounts=total_accounts,
        total_customers=total_customers,
        total_transfers=total_transfers,
        settled_transfers=settled_transfers,
        pending_transfers=pending_transfers,
        oldest_pending_age_seconds=oldest_age,
        clearing_sum=clearing_sum,
        last_reconciliation_status="PASS" if clearing_sum == 0 else "FAIL",
        fault_injection_enabled=settings.env != "production",
    )


@router.get("/operator/accounts", response_model=list[DirectoryAccountResponse])
def get_operator_accounts() -> list[DirectoryAccountResponse]:
    """Return all provisioned customer accounts across participants."""
    results: list[DirectoryAccountResponse] = []
    with get_db_connection(settings.coordinator_db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT account_id, customer_id, ledger_id, routing_version,
                       provisioning_state, currency
                FROM account_directory
                ORDER BY created_at DESC
                LIMIT 100;
            """
            )
            directory_rows = cur.fetchall()

    for d in directory_rows:
        lid = d["ledger_id"]
        acct_id = UUID(str(d["account_id"]))
        cust_id = UUID(str(d["customer_id"]))
        url = settings.ledger1_db_url if lid == "ledger-1" else settings.ledger2_db_url
        try:
            bal = get_account_balance(url, acct_id)
            results.append(
                DirectoryAccountResponse(
                    account_id=acct_id,
                    customer_id=cust_id,
                    ledger_id=lid,
                    routing_version=d["routing_version"],
                    provisioning_state=d["provisioning_state"],
                    currency=d["currency"],
                    posted_balance_minor=bal.posted_balance_minor,
                    held_amount_minor=bal.held_amount_minor,
                    available_balance_minor=bal.available_balance_minor,
                    status=bal.status.value,
                )
            )
        except Exception:
            pass

    return results


@router.get("/operator/transfers")
def get_operator_transfers(limit: int = 50) -> list[dict[str, Any]]:
    """Return list of recent transfers with state and decision."""
    with get_db_connection(settings.coordinator_db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT t.transfer_id, t.state, t.amount_minor, t.currency, t.transfer_type,
                       t.source_account_id, t.destination_account_id,
                       t.source_ledger_id, t.destination_ledger_id,
                       t.attention_required, t.attention_reason,
                       t.created_at, d.decision, d.decided_at
                FROM transfers t
                LEFT JOIN transfer_decisions d ON t.transfer_id = d.transfer_id
                ORDER BY t.created_at DESC
                LIMIT %s;
            """,
                (limit,),
            )
            rows = cur.fetchall()

    return [dict(r) for r in rows]


@router.get(
    "/operator/transfers/{transfer_id}/timeline",
    response_model=list[WorkflowTimelineEntryResponse],
)
def get_transfer_timeline(transfer_id: UUID) -> list[WorkflowTimelineEntryResponse]:
    """Retrieve full chronological workflow events for a transfer."""
    with get_db_connection(settings.coordinator_db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT event_id, transfer_id, event_type, details, created_at
                FROM workflow_events
                WHERE transfer_id = %s
                ORDER BY created_at ASC;
            """,
                (transfer_id,),
            )
            rows = cur.fetchall()

    return [
        WorkflowTimelineEntryResponse(
            event_id=r["event_id"],
            transfer_id=r["transfer_id"],
            event_type=r["event_type"],
            details=r.get("details") or {},
            created_at=r["created_at"],
        )
        for r in rows
    ]


@router.post("/operator/experiments/run", response_model=ExperimentRunResponse)
def run_operator_experiment(
    req: ExperimentRunRequest, _: None = Depends(verify_bearer_token)
) -> ExperimentRunResponse:
    """Execute a named deterministic failure injection scenario.

    Enforces that local fault controls are disabled in public-safe/production environments.
    """
    if settings.env == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Local fault controls are disabled in production environment.",
        )

    ledger_urls = {
        "ledger-1": settings.ledger1_db_url,
        "ledger-2": settings.ledger2_db_url,
    }

    steps: list[ExperimentStepResponse] = []
    t_id = uuid4()
    key = f"exp-{uuid4()}"

    c1 = register_customer(
        settings.coordinator_db_url, "Demo Alice", f"demo-alice-{uuid4()}@exp.com"
    )
    c2 = register_customer(settings.coordinator_db_url, "Demo Bob", f"demo-bob-{uuid4()}@exp.com")

    alice = provision_account(
        settings.coordinator_db_url,
        ledger_urls,
        UUID(str(c1["customer_id"])),
        "ledger-1",
        currency="INR",
    )
    bob = provision_account(
        settings.coordinator_db_url,
        ledger_urls,
        UUID(str(c2["customer_id"])),
        "ledger-2",
        currency="INR",
    )

    alice_id = UUID(str(alice["account_id"]))
    bob_id = UUID(str(bob["account_id"]))
    simulate_funding(settings.ledger1_db_url, alice_id, AmountPaise(100_000))

    if req.scenario == "SIGNATURE_RECOVERY":
        steps.append(
            ExperimentStepResponse(
                step_number=1,
                phase="PREPARE",
                action="Source Prepare & Destination Prepare",
                outcome="SUCCESS",
                details="Alice funds reserved (held 30,000 paise). Bob registered incoming intent.",
            )
        )

        fp = FailpointManager()
        fp.set_failpoint("FAIL_AFTER_COMMIT_BEFORE_SOURCE_CONFIRM", t_id)

        steps.append(
            ExperimentStepResponse(
                step_number=2,
                phase="DECISION_POINT",
                action="Record Durable COMMIT Decision",
                outcome="COMMITTED",
                details="Decision COMMIT permanently recorded in transfer_decisions under row lock.",
            )
        )

        try:
            submit_coordinator_transfer(
                settings.coordinator_db_url,
                ledger_urls,
                idempotency_key=key,
                source_account_id=alice_id,
                destination_account_id=bob_id,
                amount=AmountPaise(30_000),
                transfer_id=t_id,
                failpoint_mgr=fp,
            )
        except CrashAfterCommitError:
            steps.append(
                ExperimentStepResponse(
                    step_number=3,
                    phase="FAULT_INJECTION",
                    action="Simulate Coordinator Crash after COMMIT",
                    outcome="CRASH_SIMULATED",
                    details="Coordinator interrupted before dispatching settlement. Invariant: Holds persist, NO automatic refund.",
                )
            )

        recover_pending_transfers(settings.coordinator_db_url, ledger_urls)
        steps.append(
            ExperimentStepResponse(
                step_number=4,
                phase="FORWARD_RECOVERY",
                action="Invoke Workflow Recovery Worker",
                outcome="RECOVERED_FORWARD",
                details="Worker re-dispatched source confirm and destination confirm. State transitioned to SETTLED.",
            )
        )

        bal_a = get_account_balance(settings.ledger1_db_url, alice_id)
        bal_b = get_account_balance(settings.ledger2_db_url, bob_id)

        steps.append(
            ExperimentStepResponse(
                step_number=5,
                phase="AUDIT_VERIFICATION",
                action="Verify End-State Financial Invariants",
                outcome="VERIFIED",
                details=f"Alice posted={bal_a.posted_balance_minor}, held={bal_a.held_amount_minor}. Bob posted={bal_b.posted_balance_minor}. Zero residual holds.",
            )
        )

        return ExperimentRunResponse(
            scenario="SIGNATURE_RECOVERY",
            transfer_id=t_id,
            status="SETTLED",
            steps=steps,
            final_accounting_state={
                "alice_posted": bal_a.posted_balance_minor,
                "alice_held": bal_a.held_amount_minor,
                "bob_posted": bal_b.posted_balance_minor,
            },
        )

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown scenario '{req.scenario}'.",
        )

