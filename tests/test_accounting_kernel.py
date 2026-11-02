"""Comprehensive accounting kernel verification suite for Stage 1."""

from uuid import uuid4

import psycopg
import pytest
from hypothesis import given
from hypothesis import strategies as st

from ledgerguard.config import settings
from ledgerguard.domain.constants import SYSTEM_CASH_ACCOUNT_ID
from ledgerguard.domain.models import (
    AccountStatus,
    AccountType,
    JournalLineInput,
    JournalPostRequest,
    OperationType,
    PostingSide,
)
from ledgerguard.domain.money import (
    MAX_PAISE_AMOUNT,
    MIN_PAISE_AMOUNT,
    AmountPaise,
)
from ledgerguard.domain.templates import TemplateValidationError
from ledgerguard.participant.account_service import (
    AccountLifecycleError,
    create_ledger_account,
    get_account_balance,
    get_statement,
    set_account_status,
)
from ledgerguard.participant.posting_service import (
    PostingError,
    post_journal_entry,
    simulate_cash_out,
    simulate_funding,
)
from ledgerguard.participant.reconciliation_service import run_local_reconciliation

DB_URL = settings.ledger1_db_url
ADMIN_DB_URL = settings.ledger1_admin_db_url


# ---------------------------------------------------------------------------
# 1. Exact Monetary Arithmetic & Boundaries
# ---------------------------------------------------------------------------


def test_amount_paise_valid_boundaries():
    """Verify minimum and maximum positive paise bounds."""
    min_amt = AmountPaise(MIN_PAISE_AMOUNT)
    assert min_amt.paise == 1
    assert int(min_amt) == 1
    assert min_amt.inr_decimal_str == "0.01"

    max_amt = AmountPaise(MAX_PAISE_AMOUNT)
    assert max_amt.paise == 100_000_000_000
    assert max_amt.inr_decimal_str == "1000000000.00"

    decimal_amt = AmountPaise("125.50")
    assert decimal_amt.paise == 12550
    assert decimal_amt.inr_decimal_str == "125.50"


def test_amount_paise_invalid_values():
    """Verify rejection of floats, negatives, zeroes, booleans, and overflow."""
    with pytest.raises(TypeError, match="Floating-point amounts are strictly prohibited"):
        AmountPaise(100.5)  # type: ignore

    with pytest.raises(TypeError, match="Boolean value cannot represent an amount"):
        AmountPaise(True)  # type: ignore

    with pytest.raises(ValueError, match="Amount must be positive"):
        AmountPaise(0)

    with pytest.raises(ValueError, match="Amount must be positive"):
        AmountPaise(-100)

    with pytest.raises(ValueError, match="exceeds maximum allowed bound"):
        AmountPaise(MAX_PAISE_AMOUNT + 1)

    with pytest.raises(ValueError, match="At most 2 decimal places allowed"):
        AmountPaise("10.555")


# ---------------------------------------------------------------------------
# 2. Account Creation & Initial Balances
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_create_customer_wallet():
    """Verify customer wallet creation initializes zeroed balances."""
    account = create_ledger_account(DB_URL, account_type=AccountType.LIABILITY)
    assert account.posted_balance_minor == 0
    assert account.held_amount_minor == 0
    assert account.available_balance_minor == 0
    assert account.account_sequence == 0
    assert account.version == 0
    assert account.status == AccountStatus.ACTIVE


# ---------------------------------------------------------------------------
# 3. Funding & Cash-Out Balanced Operations
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_funding_and_cash_out_balance():
    """Verify funding increases customer balance and cash-out decreases it correctly."""
    acct = create_ledger_account(DB_URL)
    fund_amt = AmountPaise(10000)  # INR 100.00

    # 1. Fund wallet
    fund_res = simulate_funding(DB_URL, acct.account_id, fund_amt, correlation_id="fund-001")
    assert fund_res["status"] == "POSTED"

    b1 = get_account_balance(DB_URL, acct.account_id)
    assert b1.posted_balance_minor == 10000
    assert b1.available_balance_minor == 10000
    assert b1.account_sequence == 1

    # 2. Cash-out partial funds (INR 40.00)
    withdraw_amt = AmountPaise(4000)
    cashout_res = simulate_cash_out(DB_URL, acct.account_id, withdraw_amt, correlation_id="out-001")
    assert cashout_res["status"] == "POSTED"

    b2 = get_account_balance(DB_URL, acct.account_id)
    assert b2.posted_balance_minor == 6000
    assert b2.available_balance_minor == 6000
    assert b2.account_sequence == 2


@pytest.mark.integration
def test_cash_out_insufficient_funds_rejected_atomically():
    """Verify withdrawal beyond available balance is rejected without side-effects."""
    acct = create_ledger_account(DB_URL)
    simulate_funding(DB_URL, acct.account_id, AmountPaise(5000))

    # Attempt to withdraw 6000 when only 5000 is available
    with pytest.raises(PostingError, match="Insufficient"):
        simulate_cash_out(DB_URL, acct.account_id, AmountPaise(6000))

    # Balance must remain exactly 5000 and sequence remain 1
    bal = get_account_balance(DB_URL, acct.account_id)
    assert bal.posted_balance_minor == 5000
    assert bal.available_balance_minor == 5000
    assert bal.account_sequence == 1


# ---------------------------------------------------------------------------
# 4. Journal Balancing & Business Template Invariants
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_unbalanced_journal_rejected():
    """Verify unbalanced journals are rejected both in template checks and database triggers."""
    acct = create_ledger_account(DB_URL)

    # In-memory template check
    req = JournalPostRequest(
        journal_id=uuid4(),
        operation_type=OperationType.FUNDING,
        lines=[
            JournalLineInput(
                account_id=SYSTEM_CASH_ACCOUNT_ID, side=PostingSide.DEBIT, amount=AmountPaise(1000)
            ),
            JournalLineInput(
                account_id=acct.account_id, side=PostingSide.CREDIT, amount=AmountPaise(800)
            ),
        ],
    )
    with pytest.raises(TemplateValidationError, match="Unbalanced journal"):
        post_journal_entry(DB_URL, req)


@pytest.mark.integration
def test_empty_and_single_line_journal_rejected():
    """Verify journals with fewer than 2 lines cannot be posted."""
    req_empty = JournalPostRequest(
        journal_id=uuid4(),
        operation_type=OperationType.FUNDING,
        lines=[],
    )
    with pytest.raises(TemplateValidationError, match="at least 2 lines"):
        post_journal_entry(DB_URL, req_empty)


# ---------------------------------------------------------------------------
# 5. Application-Role Immutability and Direct Write Restrictions
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_application_role_cannot_directly_insert_journals():
    """Verify application role is denied direct INSERT on journal_headers."""
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute("""
                    INSERT INTO journal_headers (journal_id, operation_type)
                    VALUES (gen_random_uuid(), 'ILLEGAL_DIRECT_INSERT');
                """)


@pytest.mark.integration
def test_application_role_cannot_update_or_delete_journals():
    """Verify application role is denied direct UPDATE and DELETE on journal_headers."""
    # First post a valid journal via the posting boundary
    acct = create_ledger_account(DB_URL)
    res = simulate_funding(DB_URL, acct.account_id, AmountPaise(1000))
    jid = res["journal_id"]

    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute(
                    "UPDATE journal_headers SET description = 'TAMPERED' WHERE journal_id = %s;",
                    (jid,),
                )

    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute("DELETE FROM journal_headers WHERE journal_id = %s;", (jid,))


@pytest.mark.integration
def test_direct_truncate_is_prohibited():
    """Verify TRUNCATE is strictly denied on journal tables."""
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                cur.execute("TRUNCATE TABLE journal_headers CASCADE;")


# ---------------------------------------------------------------------------
# 6. Statement Cursor Ordering
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_deterministic_statement_order():
    """Verify statement entries are deterministically ordered by account_sequence."""
    acct = create_ledger_account(DB_URL)
    simulate_funding(DB_URL, acct.account_id, AmountPaise(1000))
    simulate_funding(DB_URL, acct.account_id, AmountPaise(2000))
    simulate_cash_out(DB_URL, acct.account_id, AmountPaise(500))

    entries, next_cursor = get_statement(DB_URL, acct.account_id, limit=2)
    assert len(entries) == 2
    assert entries[0].account_sequence == 1
    assert entries[0].amount_minor == 1000
    assert entries[1].account_sequence == 2
    assert entries[1].amount_minor == 2000
    assert next_cursor == 2

    # Fetch next page
    page2, next_cursor2 = get_statement(
        DB_URL, acct.account_id, cursor_sequence=next_cursor, limit=2
    )
    assert len(page2) == 1
    assert page2[0].account_sequence == 3
    assert page2[0].amount_minor == 500
    assert next_cursor2 is None


# ---------------------------------------------------------------------------
# 7. Account Status Lifecycle (Freeze, Close)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_account_status_lifecycle():
    """Verify freeze and close rules under account locking."""
    acct = create_ledger_account(DB_URL)
    simulate_funding(DB_URL, acct.account_id, AmountPaise(2500))

    # Cannot close account with non-zero balance
    with pytest.raises(AccountLifecycleError, match="Cannot close account"):
        set_account_status(DB_URL, acct.account_id, AccountStatus.CLOSED)

    # Freeze account
    frozen = set_account_status(DB_URL, acct.account_id, AccountStatus.FROZEN)
    assert frozen.status == AccountStatus.FROZEN

    # Unfreeze account
    active = set_account_status(DB_URL, acct.account_id, AccountStatus.ACTIVE)
    assert active.status == AccountStatus.ACTIVE

    # Withdraw all remaining funds to reach zero balance
    simulate_cash_out(DB_URL, acct.account_id, AmountPaise(2500))

    # Now closure succeeds
    closed = set_account_status(DB_URL, acct.account_id, AccountStatus.CLOSED)
    assert closed.status == AccountStatus.CLOSED

    # Postings to a CLOSED account are rejected by post_journal
    with pytest.raises(PostingError, match="is CLOSED"):
        simulate_funding(DB_URL, acct.account_id, AmountPaise(1000))


# ---------------------------------------------------------------------------
# 8. Local Reconciliation Audit
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_local_reconciliation_passes():
    """Verify initial reconciliation report passes with 0 discrepancies."""
    report = run_local_reconciliation(DB_URL)
    assert report.status == "PASS"
    assert len(report.findings) == 0
    assert report.accounts_examined > 0
    assert report.trial_balance_debit == report.trial_balance_credit


# ---------------------------------------------------------------------------
# 9. Hypothesis Property-Based Testing
# ---------------------------------------------------------------------------


@pytest.mark.property
@given(
    amt1=st.integers(min_value=1, max_value=500_000),
    amt2=st.integers(min_value=1, max_value=500_000),
)
def test_hypothesis_funding_sequences(amt1: int, amt2: int):
    """Property test verifying arbitrary positive funding sequences preserve exact balance."""
    acct = create_ledger_account(DB_URL)
    simulate_funding(DB_URL, acct.account_id, AmountPaise(amt1))
    simulate_funding(DB_URL, acct.account_id, AmountPaise(amt2))

    bal = get_account_balance(DB_URL, acct.account_id)
    assert bal.posted_balance_minor == amt1 + amt2
    assert bal.available_balance_minor == amt1 + amt2
    assert bal.account_sequence == 2
