"""Reference model comparison tests for local financial operations."""

from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest
from hypothesis import given
from hypothesis import settings as hyp_settings
from hypothesis import strategies as st

from ledgerguard.config import settings
from ledgerguard.domain.money import AmountPaise
from ledgerguard.participant.account_service import (
    create_ledger_account,
    get_account_balance,
)
from ledgerguard.participant.posting_service import (
    simulate_cash_out,
    simulate_funding,
)
from ledgerguard.participant.reconciliation_service import run_local_reconciliation
from ledgerguard.participant.transfer_service import (
    execute_local_transfer,
    execute_reversal,
)

DB_URL = settings.ledger1_db_url


@dataclass
class ReferenceWallet:
    balance: int = 0


@dataclass
class ReferenceLedgerModel:
    """Simple in-memory double-entry reference model."""

    wallets: dict[UUID, ReferenceWallet] = field(default_factory=dict)
    settled_transfers: dict[UUID, tuple[UUID, UUID, int]] = field(default_factory=dict)
    reversed_transfers: set[UUID] = field(default_factory=set)

    def add_wallet(self, acct_id: UUID) -> None:
        self.wallets[acct_id] = ReferenceWallet(balance=0)

    def deposit(self, acct_id: UUID, amount: int) -> bool:
        if amount <= 0:
            return False
        self.wallets[acct_id].balance += amount
        return True

    def withdraw(self, acct_id: UUID, amount: int) -> bool:
        if amount <= 0 or self.wallets[acct_id].balance < amount:
            return False
        self.wallets[acct_id].balance -= amount
        return True

    def transfer(self, src: UUID, dst: UUID, amount: int, transfer_id: UUID) -> bool:
        if amount <= 0 or src == dst or self.wallets[src].balance < amount:
            return False
        self.wallets[src].balance -= amount
        self.wallets[dst].balance += amount
        self.settled_transfers[transfer_id] = (src, dst, amount)
        return True

    def reverse(self, original_id: UUID) -> bool:
        if original_id not in self.settled_transfers or original_id in self.reversed_transfers:
            return False
        src, dst, amount = self.settled_transfers[original_id]
        if self.wallets[dst].balance < amount:
            return False
        self.wallets[dst].balance -= amount
        self.wallets[src].balance += amount
        self.reversed_transfers.add(original_id)
        return True


@pytest.mark.property
@hyp_settings(max_examples=15, deadline=None)
@given(
    operations=st.lists(
        st.tuples(
            st.sampled_from(["deposit", "withdraw", "transfer", "reverse"]),
            st.integers(min_value=0, max_value=2),  # source idx
            st.integers(min_value=0, max_value=2),  # dest idx
            st.integers(min_value=100, max_value=2000),  # amount
        ),
        min_size=5,
        max_size=15,
    )
)
def test_hypothesis_reference_model_agreement(operations):
    """Verify arbitrary random sequences of local operations agree exactly with ReferenceModel."""
    model = ReferenceLedgerModel()
    real_accounts: list[UUID] = []

    # Provision 3 accounts
    for _ in range(3):
        acct = create_ledger_account(DB_URL)
        real_accounts.append(acct.account_id)
        model.add_wallet(acct.account_id)

    # Initial seeding so accounts have some funds
    for aid in real_accounts:
        simulate_funding(DB_URL, aid, AmountPaise(5000))
        model.deposit(aid, 5000)

    last_transfer_id: UUID | None = None

    for op, s_idx, d_idx, amt_val in operations:
        src = real_accounts[s_idx]
        dst = real_accounts[d_idx]
        amt = AmountPaise(amt_val)

        if op == "deposit":
            simulate_funding(DB_URL, src, amt)
            model.deposit(src, amt_val)

        elif op == "withdraw":
            try:
                simulate_cash_out(DB_URL, src, amt)
                actual_ok = True
            except Exception:
                actual_ok = False
            expected_ok = model.withdraw(src, amt_val)
            assert actual_ok == expected_ok

        elif op == "transfer":
            if src == dst:
                continue
            idem_key = str(uuid4())
            try:
                res = execute_local_transfer(
                    DB_URL,
                    idempotency_key=idem_key,
                    source_account_id=src,
                    destination_account_id=dst,
                    amount=amt,
                )
                actual_ok = True
                last_transfer_id = UUID(res["transfer_id"])
            except Exception:
                actual_ok = False

            if actual_ok and last_transfer_id:
                expected_ok = model.transfer(src, dst, amt_val, last_transfer_id)
                assert expected_ok is True
            else:
                expected_ok = model.transfer(src, dst, amt_val, uuid4())
                assert expected_ok is False

        elif op == "reverse":
            if not last_transfer_id:
                continue
            try:
                execute_reversal(
                    DB_URL,
                    idempotency_key=str(uuid4()),
                    original_transfer_id=last_transfer_id,
                )
                actual_ok = True
            except Exception:
                actual_ok = False
            expected_ok = model.reverse(last_transfer_id)
            assert actual_ok == expected_ok

    # Verify all accounts match reference model
    for aid in real_accounts:
        real_bal = get_account_balance(DB_URL, aid)
        expected_bal = model.wallets[aid].balance
        assert real_bal.posted_balance_minor == expected_bal, (
            f"Account {aid} balance mismatch: real={real_bal.posted_balance_minor}, model={expected_bal}"
        )

    # Verify reconciliation passes cleanly
    report = run_local_reconciliation(DB_URL)
    assert report.status == "PASS"
    assert len(report.findings) == 0
