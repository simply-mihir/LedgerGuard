"""Reconciliation service for ledger accounts and journals."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from psycopg.rows import dict_row

from ledgerguard.db.pool import get_db_connection
from ledgerguard.domain.models import AccountType


@dataclass
class Finding:
    """Discrepancy or violation identified during reconciliation."""

    check_name: str
    severity: str
    resource_id: str
    details: str


@dataclass
class ReconciliationReport:
    """Report produced by reconciliation audit."""

    run_at: datetime
    status: str  # PASS / FAIL
    accounts_examined: int
    journals_examined: int
    lines_examined: int
    trial_balance_debit: int
    trial_balance_credit: int
    findings: list[Finding] = field(default_factory=list)


def run_local_reconciliation(db_url: str) -> ReconciliationReport:
    """Execute consistent read-only audit verifying all journals and account balances."""
    findings: list[Finding] = []

    with get_db_connection(db_url) as conn:
        cur: Any
        with conn.cursor(row_factory=dict_row) as cur:
            # 1. Check each journal: count >= 2, debits == credits
            cur.execute("""
                SELECT
                    h.journal_id,
                    COUNT(l.line_id) AS line_count,
                    COALESCE(SUM(CASE WHEN l.side = 'DEBIT' THEN l.amount_minor ELSE 0 END), 0) AS debits,
                    COALESCE(SUM(CASE WHEN l.side = 'CREDIT' THEN l.amount_minor ELSE 0 END), 0) AS credits
                FROM journal_headers h
                LEFT JOIN journal_lines l ON h.journal_id = l.journal_id
                GROUP BY h.journal_id;
            """)
            journal_rows = cur.fetchall()
            journals_examined = len(journal_rows)
            lines_examined = 0
            trial_debits = 0
            trial_credits = 0

            for jr in journal_rows:
                lines_examined += jr["line_count"]
                trial_debits += jr["debits"]
                trial_credits += jr["credits"]

                if jr["line_count"] < 2:
                    findings.append(
                        Finding(
                            check_name="MIN_LINES",
                            severity="CRITICAL",
                            resource_id=str(jr["journal_id"]),
                            details=f"Journal has {jr['line_count']} lines (minimum 2 required)",
                        )
                    )

                if jr["debits"] != jr["credits"]:
                    findings.append(
                        Finding(
                            check_name="JOURNAL_UNBALANCED",
                            severity="CRITICAL",
                            resource_id=str(jr["journal_id"]),
                            details=f"Journal unbalanced: debits={jr['debits']}, credits={jr['credits']}",
                        )
                    )

            # 2. Check each account balance cache against summed postings
            cur.execute("""
                SELECT
                    a.account_id,
                    a.account_type,
                    b.posted_balance_minor AS cached_posted,
                    b.held_amount_minor AS cached_held,
                    b.account_sequence AS cached_seq,
                    COALESCE(SUM(CASE WHEN l.side = 'DEBIT' THEN l.amount_minor ELSE 0 END), 0) AS total_debits,
                    COALESCE(SUM(CASE WHEN l.side = 'CREDIT' THEN l.amount_minor ELSE 0 END), 0) AS total_credits,
                    COUNT(l.line_id) AS total_postings
                FROM ledger_accounts a
                JOIN account_balances b ON a.account_id = b.account_id
                LEFT JOIN journal_lines l ON a.account_id = l.account_id
                GROUP BY a.account_id, a.account_type, b.posted_balance_minor, b.held_amount_minor, b.account_sequence;
            """)
            account_rows = cur.fetchall()
            accounts_examined = len(account_rows)

            for ar in account_rows:
                acct_id = ar["account_id"]
                acct_type = AccountType(ar["account_type"])
                cached_posted = ar["cached_posted"]
                total_debits = ar["total_debits"]
                total_credits = ar["total_credits"]
                cached_seq = ar["cached_seq"]
                total_postings = ar["total_postings"]

                # Expected posted balance based on account type
                if acct_type == AccountType.LIABILITY:
                    expected_posted = total_credits - total_debits
                else:
                    expected_posted = total_debits - total_credits

                if cached_posted != expected_posted:
                    findings.append(
                        Finding(
                            check_name="BALANCE_MISMATCH",
                            severity="CRITICAL",
                            resource_id=str(acct_id),
                            details=f"Account balance mismatch: cached={cached_posted}, computed={expected_posted}",
                        )
                    )

                if cached_seq != total_postings:
                    findings.append(
                        Finding(
                            check_name="SEQUENCE_MISMATCH",
                            severity="WARNING",
                            resource_id=str(acct_id),
                            details=f"Sequence mismatch: cached={cached_seq}, line count={total_postings}",
                        )
                    )

            # 3. Overall platform trial balance check
            if trial_debits != trial_credits:
                findings.append(
                    Finding(
                        check_name="TRIAL_BALANCE_UNBALANCED",
                        severity="CRITICAL",
                        resource_id="GLOBAL",
                        details=f"Platform trial balance unbalanced: debits={trial_debits}, credits={trial_credits}",
                    )
                )

    return ReconciliationReport(
        run_at=datetime.now(UTC),
        status="PASS" if not findings else "FAIL",
        accounts_examined=accounts_examined,
        journals_examined=journals_examined,
        lines_examined=lines_examined,
        trial_balance_debit=trial_debits,
        trial_balance_credit=trial_credits,
        findings=findings,
    )
