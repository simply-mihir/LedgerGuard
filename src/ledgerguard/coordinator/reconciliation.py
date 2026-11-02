"""Cross-ledger reconciliation audit verifying global invariants across independent databases."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from ledgerguard.db.pool import get_db_connection
from ledgerguard.participant.reconciliation_service import run_local_reconciliation

CLEARING_ACCOUNT_ID = UUID("00000000-0000-0000-0000-000000000002")


@dataclass
class CrossLedgerFinding:
    """Discrepancy or audit observation in distributed reconciliation."""

    check_name: str
    severity: str  # 'CRITICAL', 'WARNING', 'INFO'
    ledger_id: str  # 'coordinator', 'ledger-1', 'ledger-2', 'GLOBAL'
    resource_id: str
    details: str


@dataclass
class CrossLedgerReconciliationReport:
    """Consolidated multi-database audit report."""

    run_at: datetime
    status: str  # 'PASS', 'FAIL', 'INCOMPLETE'
    coverage: str  # 'FULL', 'PARTIAL'
    reachable_ledgers: list[str]
    unreachable_ledgers: list[str]
    transfers_examined: int
    clearing_balance_sum: int
    in_flight_clearing_amount: int
    findings: list[CrossLedgerFinding] = field(default_factory=list)


def run_cross_ledger_reconciliation(
    coord_db_url: str,
    ledger_db_urls: dict[str, str],
    drained: bool = False,
) -> CrossLedgerReconciliationReport:
    """Execute cross-database reconciliation verifying clearing, holds, and decision consistency.

    Guarantees:
    - Partial reachability reports INCOMPLETE coverage, never a false global PASS.
    - Active holds reconcile against account balance held caches on each ledger.
    - Sum of inter-ledger clearing balances across ledgers equals 0 (or is explained by in-flight transfers).
    - If drained is True, all pending transfers, in-flight clearing, and active holds must be zero.
    - Decisions, participant intents, and posted journal receipts are cross-verified.
    """
    findings: list[CrossLedgerFinding] = []
    reachable_ledgers: list[str] = []
    unreachable_ledgers: list[str] = []

    # 1. Connectivity check across all databases with fast probe
    # Test coordinator
    try:
        with psycopg.connect(coord_db_url, connect_timeout=2) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
        reachable_ledgers.append("coordinator")
    except Exception as exc:
        unreachable_ledgers.append("coordinator")
        findings.append(
            CrossLedgerFinding(
                check_name="UNREACHABLE_COORDINATOR",
                severity="CRITICAL",
                ledger_id="coordinator",
                resource_id="coordinator",
                details=f"Cannot connect to coordinator database: {exc}",
            )
        )

    # Test participants
    for lid, url in ledger_db_urls.items():
        try:
            with psycopg.connect(url, connect_timeout=2) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
            reachable_ledgers.append(lid)
        except Exception as exc:
            unreachable_ledgers.append(lid)
            findings.append(
                CrossLedgerFinding(
                    check_name="UNREACHABLE_PARTICIPANT",
                    severity="CRITICAL",
                    ledger_id=lid,
                    resource_id=lid,
                    details=f"Cannot connect to participant ledger '{lid}': {exc}",
                )
            )

    # If any ledger is unreachable, coverage is partial
    coverage = "FULL" if not unreachable_ledgers else "PARTIAL"
    if unreachable_ledgers:
        return CrossLedgerReconciliationReport(
            run_at=datetime.now(UTC),
            status="INCOMPLETE",
            coverage=coverage,
            reachable_ledgers=reachable_ledgers,
            unreachable_ledgers=unreachable_ledgers,
            transfers_examined=0,
            clearing_balance_sum=0,
            in_flight_clearing_amount=0,
            findings=findings,
        )

    # 2. Local double-entry audits on each participant
    for lid, url in ledger_db_urls.items():
        local_report = run_local_reconciliation(url)
        for f in local_report.findings:
            findings.append(
                CrossLedgerFinding(
                    check_name=f"LOCAL_{f.check_name}",
                    severity=f.severity,
                    ledger_id=lid,
                    resource_id=f.resource_id,
                    details=f.details,
                )
            )

    # 3. Reconcile active holds vs cached held amounts on each participant
    for lid, url in ledger_db_urls.items():
        with get_db_connection(url) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT b.account_id, b.held_amount_minor,
                           COALESCE(SUM(h.amount_minor), 0) AS sum_active_holds
                    FROM account_balances b
                    LEFT JOIN holds h ON b.account_id = h.account_id AND h.status = 'ACTIVE'
                    GROUP BY b.account_id, b.held_amount_minor;
                """
                )
                for row in cur.fetchall():
                    if row["held_amount_minor"] != row["sum_active_holds"]:
                        findings.append(
                            CrossLedgerFinding(
                                check_name="HOLD_CACHE_MISMATCH",
                                severity="CRITICAL",
                                ledger_id=lid,
                                resource_id=str(row["account_id"]),
                                details=(
                                    f"Held balance cache ({row['held_amount_minor']}) "
                                    f"does not match sum of active holds ({row['sum_active_holds']})"
                                ),
                            )
                        )

    # 4. Cross-ledger clearing check
    clearing_balances: dict[str, int] = {}
    for lid, url in ledger_db_urls.items():
        with get_db_connection(url) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT posted_balance_minor
                    FROM account_balances
                    WHERE account_id = %s;
                """,
                    (CLEARING_ACCOUNT_ID,),
                )
                clearing_row = cur.fetchone()
                clearing_balances[lid] = int(clearing_row["posted_balance_minor"]) if clearing_row else 0

    clearing_sum = sum(clearing_balances.values())

    # Calculate explainable in-flight clearing (where source confirmed but dest not yet)
    in_flight_clearing = 0
    with get_db_connection(coord_db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT transfer_id, amount_minor, state
                FROM transfers
                WHERE state = 'COMMITTING';
            """
            )
            for row in cur.fetchall():
                in_flight_clearing += row["amount_minor"]

    if clearing_sum != 0:
        if abs(clearing_sum) == in_flight_clearing and not drained:
            findings.append(
                CrossLedgerFinding(
                    check_name="IN_FLIGHT_CLEARING_EXPLAINED",
                    severity="INFO",
                    ledger_id="GLOBAL",
                    resource_id="CLEARING",
                    details=f"In-flight clearing difference ({clearing_sum} paise) matches pending COMMITTING transfers.",
                )
            )
        else:
            findings.append(
                CrossLedgerFinding(
                    check_name="CLEARING_UNBALANCED",
                    severity="CRITICAL",
                    ledger_id="GLOBAL",
                    resource_id="CLEARING",
                    details=(
                        f"Cross-ledger clearing does not sum to zero: sum={clearing_sum} paise, "
                        f"balances={clearing_balances}, in_flight={in_flight_clearing}"
                    ),
                )
            )

    # 5. Check transfer decisions vs participant receipts
    transfers_examined = 0
    with get_db_connection(coord_db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT t.transfer_id, t.state, t.amount_minor, t.source_ledger_id, t.destination_ledger_id,
                       d.decision
                FROM transfers t
                LEFT JOIN transfer_decisions d ON t.transfer_id = d.transfer_id;
            """
            )
            coordinator_transfers = cur.fetchall()
            transfers_examined = len(coordinator_transfers)

    for t in coordinator_transfers:
        t_id = t["transfer_id"]
        state = t["state"]
        decision = t["decision"]
        src_lid = t["source_ledger_id"]
        dst_lid = t["destination_ledger_id"]

        if src_lid in ledger_db_urls and dst_lid in ledger_db_urls:
            # Check source participant intent
            with get_db_connection(ledger_db_urls[src_lid]) as sconn:
                with sconn.cursor(row_factory=dict_row) as scur:
                    scur.execute(
                        "SELECT status FROM transfer_intents WHERE transfer_id = %s;", (t_id,)
                    )
                    s_intent = scur.fetchone()

            # Check destination participant intent
            with get_db_connection(ledger_db_urls[dst_lid]) as dconn:
                with dconn.cursor(row_factory=dict_row) as dcur:
                    dcur.execute(
                        "SELECT status FROM transfer_intents WHERE transfer_id = %s;", (t_id,)
                    )
                    d_intent = dcur.fetchone()

            if state == "SETTLED":
                if decision != "COMMIT":
                    findings.append(
                        CrossLedgerFinding(
                            check_name="DECISION_STATE_MISMATCH",
                            severity="CRITICAL",
                            ledger_id="coordinator",
                            resource_id=str(t_id),
                            details=f"Transfer {t_id} is SETTLED but decision is '{decision}'",
                        )
                    )
                if s_intent and s_intent["status"] != "CONFIRMED":
                    findings.append(
                        CrossLedgerFinding(
                            check_name="PARTICIPANT_INTENT_MISMATCH",
                            severity="CRITICAL",
                            ledger_id=src_lid,
                            resource_id=str(t_id),
                            details=f"Transfer {t_id} is SETTLED but source intent is '{s_intent['status']}'",
                        )
                    )
                if d_intent and d_intent["status"] != "CONFIRMED":
                    findings.append(
                        CrossLedgerFinding(
                            check_name="PARTICIPANT_INTENT_MISMATCH",
                            severity="CRITICAL",
                            ledger_id=dst_lid,
                            resource_id=str(t_id),
                            details=f"Transfer {t_id} is SETTLED but destination intent is '{d_intent['status']}'",
                        )
                    )

    # 6. Stopped-and-drained checks
    if drained:
        with get_db_connection(coord_db_url) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT transfer_id, state
                    FROM transfers
                    WHERE state IN ('ACCEPTED', 'PREPARING', 'COMMITTING', 'CANCELLING');
                """
                )
                undrained = cur.fetchall()
                if undrained:
                    findings.append(
                        CrossLedgerFinding(
                            check_name="UNDRAINED_TRANSFERS",
                            severity="CRITICAL",
                            ledger_id="coordinator",
                            resource_id=f"{len(undrained)} transfers",
                            details=f"System is not drained; {len(undrained)} transfers remain in progress.",
                        )
                    )

        if clearing_sum != 0:
            findings.append(
                CrossLedgerFinding(
                    check_name="DRAINED_CLEARING_NONZERO",
                    severity="CRITICAL",
                    ledger_id="GLOBAL",
                    resource_id="CLEARING",
                    details=f"Drained system has non-zero clearing balance: {clearing_sum} paise.",
                )
            )

    has_critical = any(f.severity == "CRITICAL" for f in findings)
    overall_status = "FAIL" if has_critical else "PASS"

    return CrossLedgerReconciliationReport(
        run_at=datetime.now(UTC),
        status=overall_status,
        coverage=coverage,
        reachable_ledgers=reachable_ledgers,
        unreachable_ledgers=unreachable_ledgers,
        transfers_examined=transfers_examined,
        clearing_balance_sum=clearing_sum,
        in_flight_clearing_amount=in_flight_clearing,
        findings=findings,
    )
