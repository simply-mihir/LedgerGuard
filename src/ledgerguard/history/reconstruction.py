"""As-of-time balance reconstruction using checksummed snapshots and deterministic replay."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from ledgerguard.db.pool import get_db_connection

CLEARING_ACCOUNT_ID = UUID("00000000-0000-0000-0000-000000000002")


class SnapshotMetadata(BaseModel):
    """Metadata for an immutable checksummed balance snapshot."""

    snapshot_id: str
    account_id: str
    ledger_id: str
    as_of_sequence: int
    as_of_timestamp: datetime
    posted_balance_minor: int
    held_amount_minor: int
    checksum: str


class HistoricalBalanceProof(BaseModel):
    """Verifiable proof of an account's posted, held, and available balance at time T."""

    account_id: str
    ledger_id: str
    as_of: datetime
    snapshot_used: SnapshotMetadata | None = None
    entries_replayed: int
    holds_active_at_t: int
    posted_balance_minor: int
    held_amount_minor: int
    available_balance_minor: int
    verification_status: str  # VERIFIED, SNAPSHOT_CORRUPTED, INCOMPLETE
    present_posted_balance_minor: int | None = None
    included_entries: list[dict[str, Any]] = Field(default_factory=list)
    excluded_entries: list[dict[str, Any]] = Field(default_factory=list)
    reason: str = ""


class ClearingAsOfReport(BaseModel):
    """Cross-ledger clearing balance reconstruction at time T."""

    as_of: datetime
    status: str  # VERIFIED, INCOMPLETE
    ledger_clearing_minor: dict[str, int] = Field(default_factory=dict)
    net_clearing_delta_minor: int = 0
    reason: str = ""


def compute_snapshot_checksum(
    *,
    account_id: str,
    ledger_id: str,
    as_of_sequence: int,
    as_of_timestamp: datetime,
    posted_balance_minor: int,
    held_amount_minor: int,
) -> str:
    """Compute canonical SHA-256 checksum for a balance snapshot."""
    ts = as_of_timestamp.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    payload = (
        f"LEDGERGUARD_SNAPSHOT_V1|{account_id}|{ledger_id}|"
        f"{as_of_sequence}|{ts}|{posted_balance_minor}|{held_amount_minor}"
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def create_account_snapshot(
    ledger_db_url: str,
    account_id: UUID,
    ledger_id: str,
) -> SnapshotMetadata:
    """Capture an immutable checksummed snapshot of an account's current balance and sequence."""
    with get_db_connection(ledger_db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT b.posted_balance_minor, b.held_amount_minor, b.account_sequence, NOW() AS snap_ts
                FROM account_balances b
                WHERE b.account_id = %s;
                """,
                (account_id,),
            )
            bal = cur.fetchone()
            if not bal:
                raise ValueError(f"Account {account_id} not found on {ledger_id}")

            cur.execute(
                """
                SELECT COALESCE(MAX(h.sequence_number), 0) AS max_seq
                FROM journal_headers h
                JOIN journal_lines l ON h.journal_id = l.journal_id
                WHERE l.account_id = %s;
                """,
                (account_id,),
            )
            seq_row = cur.fetchone()
            seq = int(seq_row["max_seq"]) if seq_row else 0
            snap_ts: datetime = bal["snap_ts"]
            posted = int(bal["posted_balance_minor"])
            held = int(bal["held_amount_minor"])

            checksum = compute_snapshot_checksum(
                account_id=str(account_id),
                ledger_id=ledger_id,
                as_of_sequence=seq,
                as_of_timestamp=snap_ts,
                posted_balance_minor=posted,
                held_amount_minor=held,
            )

            snap_id = uuid4()
            cur.execute(
                """
                INSERT INTO balance_snapshots (
                    snapshot_id, account_id, ledger_id, as_of_sequence,
                    as_of_timestamp, posted_balance_minor, held_amount_minor, checksum
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (account_id, as_of_sequence) DO NOTHING;
                """,
                (snap_id, account_id, ledger_id, seq, snap_ts, posted, held, checksum),
            )
            cur.execute(
                """
                SELECT snapshot_id, account_id, ledger_id, as_of_sequence,
                       as_of_timestamp, posted_balance_minor, held_amount_minor, checksum
                FROM balance_snapshots
                WHERE account_id = %s AND as_of_sequence = %s;
                """,
                (account_id, seq),
            )
            row = cur.fetchone()
            assert row is not None
        conn.commit()

    return SnapshotMetadata(
        snapshot_id=str(row["snapshot_id"]),
        account_id=str(row["account_id"]),
        ledger_id=str(row["ledger_id"]),
        as_of_sequence=int(row["as_of_sequence"]),
        as_of_timestamp=row["as_of_timestamp"],
        posted_balance_minor=int(row["posted_balance_minor"]),
        held_amount_minor=int(row["held_amount_minor"]),
        checksum=str(row["checksum"]),
    )


def _line_delta(account_type: str, side: str, amount_minor: int) -> int:
    if account_type == "LIABILITY":
        return amount_minor if side == "CREDIT" else -amount_minor
    return amount_minor if side == "DEBIT" else -amount_minor


def select_as_of_prefix(
    lines: list[dict[str, Any]], acct_type: str, as_of_utc: datetime
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """Split an account's lines (already in account-sequence order) into those "as of T" and the rest.

    "As of T" is a *prefix* of the sequence: inclusion stops at the first line stamped after T. A wall-clock
    step backwards can stamp a later entry earlier than T while an earlier entry is stamped after it;
    including the later one alone would show a balance that never existed.
    Returns ``(included, excluded, posted_balance_delta)``.
    """
    included: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    posted = 0
    in_prefix = True
    for ln in lines:
        ts = ln["created_at"].astimezone(UTC)
        entry = {
            "journal_id": str(ln["journal_id"]),
            "sequence_number": ln["sequence_number"],
            "operation_type": ln["operation_type"],
            "side": ln["side"],
            "amount_minor": int(ln["amount_minor"]),
            "created_at": ts.isoformat(),
        }
        in_prefix = in_prefix and ts <= as_of_utc
        if in_prefix:
            posted += _line_delta(acct_type, str(ln["side"]), int(ln["amount_minor"]))
            included.append(entry)
        else:
            excluded.append(entry)
    return included, excluded, posted


def reconstruct_account_balance_as_of(
    ledger_db_url: str,
    account_id: UUID,
    as_of: datetime,
    *,
    ledger_id: str = "ledger-1",
    use_snapshots: bool = True,
) -> HistoricalBalanceProof:
    """Reconstruct posted, held, and available balances at historical timestamp `as_of`."""
    as_of_utc = as_of.astimezone(UTC) if as_of.tzinfo else as_of.replace(tzinfo=UTC)

    with get_db_connection(ledger_db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT a.account_id, a.account_type, a.created_at, b.posted_balance_minor
                FROM ledger_accounts a
                JOIN account_balances b ON a.account_id = b.account_id
                WHERE a.account_id = %s;
                """,
                (account_id,),
            )
            acct = cur.fetchone()
            if not acct:
                raise ValueError(f"Account {account_id} not found on {ledger_id}")

            created_at: datetime = acct["created_at"]
            if as_of_utc < created_at.astimezone(UTC):
                raise ValueError(
                    f"Timestamp {as_of_utc.isoformat()} precedes account creation ({created_at.isoformat()})."
                )

            cur.execute(
                """
                SELECT h.journal_id, h.sequence_number, h.operation_type, h.created_at,
                       l.line_no, l.side, l.amount_minor, l.account_sequence
                FROM journal_lines l
                JOIN journal_headers h ON l.journal_id = h.journal_id
                WHERE l.account_id = %s
                ORDER BY l.account_sequence ASC NULLS LAST, h.sequence_number ASC NULLS LAST, h.created_at ASC,
                         h.journal_id ASC, l.line_no ASC;
                """,
                (account_id,),
            )
            all_lines = cur.fetchall()

            cur.execute(
                """
                SELECT hold_id, transfer_id, amount_minor, status, created_at, updated_at
                FROM holds
                WHERE account_id = %s AND created_at <= %s
                ORDER BY created_at ASC;
                """,
                (account_id, as_of_utc),
            )
            hold_rows = cur.fetchall()

            snap_row = None
            if use_snapshots:
                cur.execute(
                    """
                    SELECT snapshot_id, account_id, ledger_id, as_of_sequence,
                           as_of_timestamp, posted_balance_minor, held_amount_minor, checksum
                    FROM balance_snapshots
                    WHERE account_id = %s AND as_of_timestamp <= %s
                    ORDER BY as_of_sequence DESC, as_of_timestamp DESC
                    LIMIT 1;
                    """,
                    (account_id, as_of_utc),
                )
                snap_row = cur.fetchone()

    acct_type = str(acct["account_type"])
    present_posted = int(acct["posted_balance_minor"])

    # Compute active holds at time T
    active_holds = [
        h
        for h in hold_rows
        if h["status"] == "ACTIVE" or h["updated_at"].astimezone(UTC) > as_of_utc
    ]
    held_at_t = sum(int(h["amount_minor"]) for h in active_holds)

    # Full replay baseline (used for verification & fallback)
    included, excluded, full_posted = select_as_of_prefix(all_lines, acct_type, as_of_utc)

    snapshot_meta: SnapshotMetadata | None = None
    verification_status = "VERIFIED"
    posted_result = full_posted
    entries_replayed = len(included)
    reason = "Full deterministic journal replay verified."

    if snap_row is not None:
        expected_sum = compute_snapshot_checksum(
            account_id=str(snap_row["account_id"]),
            ledger_id=str(snap_row["ledger_id"]),
            as_of_sequence=int(snap_row["as_of_sequence"]),
            as_of_timestamp=snap_row["as_of_timestamp"],
            posted_balance_minor=int(snap_row["posted_balance_minor"]),
            held_amount_minor=int(snap_row["held_amount_minor"]),
        )
        if expected_sum != str(snap_row["checksum"]):
            verification_status = "SNAPSHOT_CORRUPTED"
            reason = f"Snapshot {snap_row['snapshot_id']} failed checksum verification; fell back to full replay."
        else:
            snapshot_meta = SnapshotMetadata(
                snapshot_id=str(snap_row["snapshot_id"]),
                account_id=str(snap_row["account_id"]),
                ledger_id=str(snap_row["ledger_id"]),
                as_of_sequence=int(snap_row["as_of_sequence"]),
                as_of_timestamp=snap_row["as_of_timestamp"],
                posted_balance_minor=int(snap_row["posted_balance_minor"]),
                held_amount_minor=int(snap_row["held_amount_minor"]),
                checksum=str(snap_row["checksum"]),
            )
            snap_seq = snapshot_meta.as_of_sequence
            snap_posted = snapshot_meta.posted_balance_minor
            delta_after_snap = 0
            replayed_after_snap = 0
            for ln in all_lines:
                ts = ln["created_at"].astimezone(UTC)
                seq = int(ln["sequence_number"] or 0)
                if ts <= as_of_utc and seq > snap_seq:
                    delta_after_snap += _line_delta(acct_type, str(ln["side"]), int(ln["amount_minor"]))
                    replayed_after_snap += 1
            snap_plus_replay = snap_posted + delta_after_snap
            if snap_plus_replay != full_posted:
                verification_status = "SNAPSHOT_CORRUPTED"
                reason = "Snapshot + replay diverged from full replay; fell back to full replay."
            else:
                posted_result = snap_plus_replay
                entries_replayed = replayed_after_snap
                reason = f"Verified snapshot {snapshot_meta.snapshot_id} + {replayed_after_snap} replayed entries."

    return HistoricalBalanceProof(
        account_id=str(account_id),
        ledger_id=ledger_id,
        as_of=as_of_utc,
        snapshot_used=snapshot_meta,
        entries_replayed=entries_replayed,
        holds_active_at_t=len(active_holds),
        posted_balance_minor=posted_result,
        held_amount_minor=held_at_t,
        available_balance_minor=posted_result - held_at_t,
        verification_status=verification_status,
        present_posted_balance_minor=present_posted,
        included_entries=included,
        excluded_entries=excluded,
        reason=reason,
    )


def reconstruct_clearing_as_of(
    ledger1_db_url: str,
    ledger2_db_url: str,
    as_of: datetime,
) -> ClearingAsOfReport:
    """Reconstruct inter-ledger clearing balance across Ledger 1 and Ledger 2 at time T."""
    as_of_utc = as_of.astimezone(UTC) if as_of.tzinfo else as_of.replace(tzinfo=UTC)
    clearing: dict[str, int] = {}
    for lid, url in (("ledger-1", ledger1_db_url), ("ledger-2", ledger2_db_url)):
        try:
            proof = reconstruct_account_balance_as_of(
                url, CLEARING_ACCOUNT_ID, as_of_utc, ledger_id=lid, use_snapshots=False
            )
            clearing[lid] = proof.posted_balance_minor
        except Exception as exc:
            return ClearingAsOfReport(
                as_of=as_of_utc,
                status="INCOMPLETE",
                ledger_clearing_minor=clearing,
                reason=f"Unable to reconstruct {lid} clearing balance: {exc}",
            )

    net = sum(clearing.values())
    return ClearingAsOfReport(
        as_of=as_of_utc,
        status="VERIFIED",
        ledger_clearing_minor=clearing,
        net_clearing_delta_minor=net,
        reason="Reconstructed clearing balances across both participant ledgers.",
    )
