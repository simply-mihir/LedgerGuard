#!/usr/bin/env python3
"""LedgerGuard — Signature Scenario: Interrupted 2PC Recovery Demo.

Demonstrates:
1. Phase 1 Prepare: Alice reserves funds (hold created on Ledger 1).
2. Coordinator commits durable decision (COMMIT recorded in Coordinator DB).
3. Coordinator crash injected before Phase 2 confirmation.
4. Inspection of durable interrupted state:
   - Decision is committed (COMMIT)
   - Hold remains ACTIVE on Ledger 1
   - Bob has NOT yet been credited on Ledger 2
   - Zero premature refund / rollback
5. Worker forward recovery restarts and settles Phase 2:
   - Source settlement consumes Alice's hold and debits clearing
   - Destination settlement credits Bob and credits clearing
   - Zero residual holds
   - Exact single credit
   - Zero net clearing discrepancy across independent databases.
"""

from __future__ import annotations

import os
import sys
import time
from uuid import uuid4

from psycopg.rows import dict_row

from ledgerguard.coordinator.directory_service import (
    provision_account,
    register_customer,
)
from ledgerguard.coordinator.failpoints import (
    CrashAfterCommitError,
    FailpointManager,
)
from ledgerguard.coordinator.reconciliation import run_cross_ledger_reconciliation
from ledgerguard.coordinator.transfer_coordinator import submit_coordinator_transfer
from ledgerguard.db.pool import get_db_connection
from ledgerguard.domain.constants import SYSTEM_CLEARING_ACCOUNT_ID
from ledgerguard.domain.money import AmountPaise
from ledgerguard.participant.account_service import get_account_balance
from ledgerguard.participant.posting_service import simulate_funding
from ledgerguard.worker.orchestrator import recover_pending_transfers

# Colors for terminal output
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
RESET = "\033[0m"


def print_banner(text: str) -> None:
    print(f"\n{BOLD}{CYAN}{'=' * 75}{RESET}")
    print(f"{BOLD}{CYAN}  {text}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 75}{RESET}\n")


def print_step(num: int, title: str) -> None:
    print(f"\n{BOLD}{YELLOW}[STEP {num}] {title}{RESET}")


def format_inr(paise: int) -> str:
    sign = "-" if paise < 0 else ""
    abs_p = abs(paise)
    rupees = abs_p // 100
    remainder = abs_p % 100
    return f"{sign}₹{rupees:,}.{remainder:02d}"


def run_demo() -> int:
    coord_db = os.getenv("LEDGERGUARD_COORDINATOR_DB_URL", "postgresql://ledgerguard_app:ledgerguard_app_secret@localhost:5442/coordinator_db")
    l1_db = os.getenv("LEDGERGUARD_LEDGER1_DB_URL", "postgresql://ledgerguard_app:ledgerguard_app_secret@localhost:5443/ledger1_db")
    l2_db = os.getenv("LEDGERGUARD_LEDGER2_DB_URL", "postgresql://ledgerguard_app:ledgerguard_app_secret@localhost:5444/ledger2_db")

    ledger_urls = {
        "ledger-1": l1_db,
        "ledger-2": l2_db,
    }

    print_banner("LEDGERGUARD SIGNATURE FAILURE SCENARIO: INTERRUPTED 2PC RECOVERY")

    # Step 1: Provisioning & Funding
    print_step(1, "Provisioning Isolated Participants & Seeding Accounts")
    run_id = uuid4().hex[:6]
    cust_alice = register_customer(coord_db, f"Alice {run_id}", f"alice-{run_id}@example.com")
    cust_bob = register_customer(coord_db, f"Bob {run_id}", f"bob-{run_id}@example.com")

    alice_acc = provision_account(coord_db, ledger_urls, cust_alice["customer_id"], "ledger-1")
    bob_acc = provision_account(coord_db, ledger_urls, cust_bob["customer_id"], "ledger-2")

    alice_id = alice_acc["account_id"]
    bob_id = bob_acc["account_id"]

    # Fund Alice with ₹1,000.00 (100,000 paise)
    simulate_funding(l1_db, alice_id, AmountPaise(100_000), correlation_id=f"seed-{run_id}")

    alice_bal = get_account_balance(l1_db, alice_id)
    bob_bal = get_account_balance(l2_db, bob_id)
    l1_clearing_init = get_account_balance(l1_db, SYSTEM_CLEARING_ACCOUNT_ID)
    l2_clearing_init = get_account_balance(l2_db, SYSTEM_CLEARING_ACCOUNT_ID)

    print(f"  • Source Customer:      Alice on Ledger 1 ({alice_id})")
    print(f"    - Posted Balance:     {GREEN}{format_inr(alice_bal.posted_balance_minor)}{RESET}")
    print(f"    - Available Balance:  {GREEN}{format_inr(alice_bal.available_balance_minor)}{RESET}")
    print(f"    - Active Holds:       {format_inr(alice_bal.held_amount_minor)}")
    print(f"  • Destination Customer: Bob on Ledger 2 ({bob_id})")
    print(f"    - Posted Balance:     {GREEN}{format_inr(bob_bal.posted_balance_minor)}{RESET}")
    print(f"    - Available Balance:  {GREEN}{format_inr(bob_bal.available_balance_minor)}{RESET}")

    # Step 2: Inject Coordinator Crash After COMMIT
    transfer_amt = AmountPaise(40_000)  # ₹400.00
    transfer_id = uuid4()
    idempotency_key = f"demo-tx-{transfer_id}"

    print_step(2, f"Executing 2PC Cross-Ledger Transfer ({format_inr(transfer_amt.paise)}) with Failpoint")
    print(f"  • Injected Fault: {RED}{BOLD}FAIL_AFTER_COMMIT_BEFORE_SOURCE_CONFIRM{RESET}")
    print("    Simulates a fatal coordinator crash immediately after the COMMIT decision is durably logged,")
    print("    before any Phase 2 confirmations reach participant ledgers.")

    fp = FailpointManager()
    fp.set_failpoint("FAIL_AFTER_COMMIT_BEFORE_SOURCE_CONFIRM", transfer_id)

    crash_caught = False
    try:
        submit_coordinator_transfer(
            coord_db,
            ledger_urls,
            idempotency_key=idempotency_key,
            source_account_id=alice_id,
            destination_account_id=bob_id,
            amount=transfer_amt,
            transfer_id=transfer_id,
            failpoint_mgr=fp,
        )
    except CrashAfterCommitError as ex:
        crash_caught = True
        print(f"\n  {RED}⚡ CRASH INJECTED:{RESET} {ex}")

    if not crash_caught:
        print(f"{RED}Error: Expected CrashAfterCommitError was not triggered!{RESET}")
        return 1

    # Step 3: Inspect Invariants in Interrupted State
    print_step(3, "Inspecting Invariants During Coordinator Outage")

    # 1. Coordinator DB check
    with get_db_connection(coord_db) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT state FROM transfers WHERE transfer_id = %s;", (transfer_id,))
            tx_row = cur.fetchone()
            cur.execute("SELECT decision FROM transfer_decisions WHERE transfer_id = %s;", (transfer_id,))
            dec_row = cur.fetchone()

    # 2. Ledger 1 state
    alice_bal_interrupted = get_account_balance(l1_db, alice_id)
    # 3. Ledger 2 state
    bob_bal_interrupted = get_account_balance(l2_db, bob_id)

    print(f"  1. Coordinator Transfer State:   {YELLOW}{tx_row['state'] if tx_row else 'None'}{RESET}")
    print(f"  2. Coordinator Durable Decision: {BOLD}{GREEN}{dec_row['decision'] if dec_row else 'None'}{RESET} (Committed to disk)")
    print(f"  3. Alice (Ledger 1) Hold:        {RED}{format_inr(alice_bal_interrupted.held_amount_minor)}{RESET} (Reserved, NOT refunded)")
    print(f"  4. Alice Available Spendability: {format_inr(alice_bal_interrupted.available_balance_minor)}")
    print(f"  5. Bob (Ledger 2) Balance:       {format_inr(bob_bal_interrupted.posted_balance_minor)} (Awaiting Phase 2 confirmation)")

    assert dec_row and dec_row["decision"] == "COMMIT", "Invariant violation: Decision must be COMMIT"
    assert alice_bal_interrupted.held_amount_minor == 40_000, "Invariant violation: Source hold must remain active"
    assert bob_bal_interrupted.posted_balance_minor == 0, "Invariant violation: Destination must not be prematurely credited"
    print(f"\n  {GREEN}✓ ALL INVARIANTS SATISFIED DURING CRASH:{RESET} Zero premature refund, durable reservation held.")

    # Step 4: Worker Forward Recovery
    print_step(4, "Starting Autonomous Worker Forward Recovery")
    print("  Orchestrator discovers transfer in COMMITTED state:")
    print("  Applying source-first settlement on Ledger 1 -> Settlement on Ledger 2.")

    time.sleep(1)  # small pause for visual clarity
    recovered = recover_pending_transfers(coord_db, ledger_urls, transfer_id=transfer_id)

    recovered_entry = next((r for r in recovered if r["transfer_id"] == str(transfer_id)), None)
    if not recovered_entry or recovered_entry["status"] != "SETTLED":
        print(f"{RED}Error: Transfer failed to recover forward to SETTLED!{RESET}")
        return 1

    print(f"  {GREEN}✓ Forward Recovery Result:{RESET} Transfer {transfer_id} status = {BOLD}{GREEN}SETTLED{RESET}")

    # Step 5: Final State & Settlement Verification
    print_step(5, "Verifying Final End-State Balances & Clearing Invariant")

    alice_bal_final = get_account_balance(l1_db, alice_id)
    bob_bal_final = get_account_balance(l2_db, bob_id)

    print("  • Alice on Ledger 1:")
    print(f"    - Posted Balance:    {BOLD}{GREEN}{format_inr(alice_bal_final.posted_balance_minor)}{RESET} (Expected: ₹600.00)")
    print(f"    - Active Holds:      {format_inr(alice_bal_final.held_amount_minor)} (Expected: ₹0.00)")
    print(f"    - Available:         {format_inr(alice_bal_final.available_balance_minor)}")
    print("  • Bob on Ledger 2:")
    print(f"    - Posted Balance:    {BOLD}{GREEN}{format_inr(bob_bal_final.posted_balance_minor)}{RESET} (Expected: ₹400.00)")
    print(f"    - Available:         {format_inr(bob_bal_final.available_balance_minor)}")

    l1_clearing_final = get_account_balance(l1_db, SYSTEM_CLEARING_ACCOUNT_ID)
    l2_clearing_final = get_account_balance(l2_db, SYSTEM_CLEARING_ACCOUNT_ID)
    delta_l1 = l1_clearing_final.posted_balance_minor - l1_clearing_init.posted_balance_minor
    delta_l2 = l2_clearing_final.posted_balance_minor - l2_clearing_init.posted_balance_minor

    print("  • Inter-Ledger Clearing Movement:")
    print(f"    - Ledger 1 Clearing Delta: {format_inr(delta_l1)}")
    print(f"    - Ledger 2 Clearing Delta: {format_inr(delta_l2)}")
    print(f"    - Net Clearing Delta:      {BOLD}{GREEN}{format_inr(delta_l1 + delta_l2)}{RESET} (Exact Conservation)")

    assert alice_bal_final.posted_balance_minor == 60_000
    assert alice_bal_final.held_amount_minor == 0
    assert bob_bal_final.posted_balance_minor == 40_000
    assert delta_l1 + delta_l2 == 0, "Invariant violation: Inter-ledger clearing must balance to zero"

    # Step 6: External Idempotency Retry Verification
    print_step(6, "Demonstrating External Client Idempotency Retry")
    print(f"  • Retrying transfer submission with identical idempotency key: {idempotency_key}")
    retry_res = submit_coordinator_transfer(
        coord_db,
        ledger_urls,
        idempotency_key=idempotency_key,
        source_account_id=alice_id,
        destination_account_id=bob_id,
        amount=transfer_amt,
        transfer_id=transfer_id,
    )
    print(f"  • Retry Response Status: {BOLD}{GREEN}{retry_res['status']}{RESET}")
    print(f"  • Matched Transfer ID:   {retry_res['transfer_id']}")
    assert retry_res["status"] == "SETTLED", "Retry must return SETTLED"
    assert retry_res["transfer_id"] == str(transfer_id), "Retry must return original transfer_id"

    # Verify balances were not double-applied
    alice_bal_retry = get_account_balance(l1_db, alice_id)
    bob_bal_retry = get_account_balance(l2_db, bob_id)
    assert alice_bal_retry.posted_balance_minor == 60_000, "Alice balance must remain 60,000 paise after retry"
    assert bob_bal_retry.posted_balance_minor == 40_000, "Bob balance must remain 40,000 paise after retry"
    print(f"  {GREEN}✓ Zero Duplicate Financial Effect:{RESET} Balances unchanged after repeated client retry.")

    # Step 7: Inspect Participant Journal Counts & Inbox Receipts
    print_step(7, "Inspecting Participant Journal Entries and Command Receipts")
    with get_db_connection(l1_db) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) as count FROM journal_headers WHERE correlation_id LIKE %s;",
                (f"%{transfer_id}%",),
            )
            l1_journal_count = cur.fetchone()["count"]
            cur.execute(
                "SELECT count(*) as count FROM command_inbox WHERE transfer_id = %s;",
                (transfer_id,),
            )
            l1_inbox_count = cur.fetchone()["count"]

    with get_db_connection(l2_db) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) as count FROM journal_headers WHERE correlation_id LIKE %s;",
                (f"%{transfer_id}%",),
            )
            l2_journal_count = cur.fetchone()["count"]
            cur.execute(
                "SELECT count(*) as count FROM command_inbox WHERE transfer_id = %s;",
                (transfer_id,),
            )
            l2_inbox_count = cur.fetchone()["count"]

    print(f"  • Ledger 1 (Source) Journals for Transfer:      {BOLD}{GREEN}{l1_journal_count}{RESET} (Expected: 1 settlement journal)")
    print(f"  • Ledger 1 (Source) Inbox Receipts for Transfer: {BOLD}{GREEN}{l1_inbox_count}{RESET} (Prepare + Confirm receipts)")
    print(f"  • Ledger 2 (Dest) Journals for Transfer:        {BOLD}{GREEN}{l2_journal_count}{RESET} (Expected: 1 settlement journal)")
    print(f"  • Ledger 2 (Dest) Inbox Receipts for Transfer:   {BOLD}{GREEN}{l2_inbox_count}{RESET} (Prepare + Confirm receipts)")

    assert l1_journal_count == 1, f"Expected 1 settlement journal on Ledger 1, got {l1_journal_count}"
    assert l2_journal_count == 1, f"Expected 1 settlement journal on Ledger 2, got {l2_journal_count}"
    assert l1_inbox_count >= 1, "Expected inbox receipts on Ledger 1"
    assert l2_inbox_count >= 1, "Expected inbox receipts on Ledger 2"

    # Step 8: Multi-Database Stopped-and-Drained Reconciliation
    print_step(8, "Executing Final Stopped-and-Drained Cross-Ledger Audit")
    report = run_cross_ledger_reconciliation(
        coord_db_url=coord_db,
        ledger_db_urls=ledger_urls,
        drained=True,
    )

    print(f"  • Audit Status:         {GREEN if report.status == 'PASS' else RED}{report.status}{RESET}")
    print(f"  • Audit Coverage:       {report.coverage}")
    print(f"  • Reachable Ledgers:    {', '.join(report.reachable_ledgers)}")
    print(f"  • Transfers Examined:   {report.transfers_examined}")
    print(f"  • Findings Count:       {len(report.findings)}")

    assert report.status == "PASS", f"Reconciliation audit failed with status {report.status}: {report.findings}"
    assert len(report.findings) == 0, f"Expected 0 findings, got {len(report.findings)}"

    print_banner("DEMO COMPLETED SUCCESSFULLY: ZERO FUNDS LOST, FORWARD RECOVERY VERIFIED")
    return 0


if __name__ == "__main__":
    sys.exit(run_demo())
