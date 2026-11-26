"""Canonical SHA-256 hash-chain and Merkle checkpoint verification for LedgerGuard journals."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from ledgerguard.config import settings
from ledgerguard.db.pool import get_db_connection

GENESIS_HASH = "0" * 64
DOMAIN_SEPARATOR = "LEDGERGUARD_JOURNAL_V1"


class ChainVerificationReport(BaseModel):
    """Result of verifying a ledger's sequential journal hash chain."""

    ledger_id: str
    status: str  # PASS, FAIL, INCOMPLETE
    verified_range: dict[str, int] = Field(default_factory=lambda: {"first": 0, "last": 0})
    entries_checked: int = 0
    first_broken_sequence: int | None = None
    expected_hash: str | None = None
    observed_hash: str | None = None
    missing_or_duplicated_sequence: int | None = None
    reason: str = ""


class CheckpointAttestationResult(BaseModel):
    """Created Merkle checkpoint and coordinator attestation record."""

    checkpoint_id: str
    ledger_id: str
    first_sequence: int
    last_sequence: int
    merkle_root: str
    leaf_count: int
    schema_version: int = 1
    attested_in_coordinator: bool = True


class CheckpointVerificationReport(BaseModel):
    """Result of verifying a Merkle checkpoint against ledger entries and coordinator attestation."""

    ledger_id: str
    checkpoint_id: str | None = None
    status: str  # PASS, FAIL, INCOMPLETE
    verified_range: dict[str, int] = Field(default_factory=lambda: {"first": 0, "last": 0})
    expected_merkle_root: str | None = None
    observed_merkle_root: str | None = None
    attested_merkle_root: str | None = None
    affected_checkpoint: str | None = None
    reason: str = ""


def _format_utc_canonical(ts: datetime) -> str:
    utc_dt = ts.astimezone(UTC)
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def compute_entry_hash(
    *,
    schema_version: int,
    ledger_id: str,
    sequence_number: int,
    previous_hash: str,
    journal_id: str,
    created_at: datetime,
    operation_type: str,
    currency: str,
    transfer_id: str | None,
    lines: list[dict[str, Any]],
) -> str:
    """Compute canonical SHA-256 hash matching PostgreSQL compute_journal_entry_hash."""
    ordered_lines = sorted(lines, key=lambda x: int(x["line_no"]))
    lines_str = ";".join(
        f"{int(ln['line_no'])}:{ln['account_id']}:{ln['side']}:{int(ln['amount_minor'])}"
        for ln in ordered_lines
    )
    payload = "|".join(
        [
            DOMAIN_SEPARATOR,
            str(schema_version),
            ledger_id,
            str(sequence_number),
            previous_hash,
            str(journal_id),
            _format_utc_canonical(created_at),
            operation_type,
            currency,
            str(transfer_id) if transfer_id else "",
            lines_str,
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_merkle_root(hashes: list[str]) -> str:
    """Compute deterministic binary SHA-256 Merkle root over a non-empty list of hex hashes."""
    if not hashes:
        return GENESIS_HASH
    level = list(hashes)
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        next_level: list[str] = []
        for i in range(0, len(level), 2):
            combined = f"NODE|{level[i]}|{level[i + 1]}".encode()
            next_level.append(hashlib.sha256(combined).hexdigest())
        level = next_level
    return level[0]


def verify_journal_chain(ledger_db_url: str, ledger_id: str) -> ChainVerificationReport:
    """Verify the entire sequential hash chain for a participant ledger."""
    try:
        with get_db_connection(ledger_db_url) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT journal_id, ledger_id, sequence_number, previous_hash, entry_hash,
                           hash_schema_version, operation_type, currency, transfer_id, created_at
                    FROM journal_headers
                    ORDER BY sequence_number ASC NULLS FIRST, created_at ASC;
                    """
                )
                headers = cur.fetchall()
                cur.execute(
                    """
                    SELECT journal_id, line_no, account_id, side, amount_minor
                    FROM journal_lines
                    ORDER BY journal_id ASC, line_no ASC;
                    """
                )
                all_lines = cur.fetchall()
    except Exception as exc:
        return ChainVerificationReport(
            ledger_id=ledger_id,
            status="INCOMPLETE",
            reason=f"Database unreachable: {exc}",
        )

    if not headers:
        return ChainVerificationReport(
            ledger_id=ledger_id,
            status="PASS",
            verified_range={"first": 0, "last": 0},
            entries_checked=0,
            reason="Empty journal chain.",
        )

    lines_by_journal: dict[str, list[dict[str, Any]]] = {}
    for ln in all_lines:
        jid = str(ln["journal_id"])
        lines_by_journal.setdefault(jid, []).append(dict(ln))

    expected_seq = 1
    expected_prev = GENESIS_HASH

    for hdr in headers:
        seq = hdr["sequence_number"]
        if seq is None or int(seq) != expected_seq:
            return ChainVerificationReport(
                ledger_id=ledger_id,
                status="FAIL",
                verified_range={"first": 1 if expected_seq > 1 else 0, "last": expected_seq - 1},
                entries_checked=expected_seq - 1,
                first_broken_sequence=expected_seq,
                missing_or_duplicated_sequence=expected_seq if seq is None or int(seq) > expected_seq else int(seq),
                reason=f"Sequence gap or duplication: expected {expected_seq}, observed {seq}",
            )

        if hdr["previous_hash"] != expected_prev:
            return ChainVerificationReport(
                ledger_id=ledger_id,
                status="FAIL",
                verified_range={"first": 1 if expected_seq > 1 else 0, "last": expected_seq - 1},
                entries_checked=expected_seq - 1,
                first_broken_sequence=expected_seq,
                expected_hash=expected_prev,
                observed_hash=hdr["previous_hash"],
                reason=f"Previous hash mismatch at sequence {expected_seq}",
            )

        jid = str(hdr["journal_id"])
        expected_entry_hash = compute_entry_hash(
            schema_version=int(hdr["hash_schema_version"]),
            ledger_id=str(hdr["ledger_id"]),
            sequence_number=int(seq),
            previous_hash=str(hdr["previous_hash"]),
            journal_id=jid,
            created_at=hdr["created_at"],
            operation_type=str(hdr["operation_type"]),
            currency=str(hdr["currency"]),
            transfer_id=str(hdr["transfer_id"]) if hdr["transfer_id"] else None,
            lines=lines_by_journal.get(jid, []),
        )
        if hdr["entry_hash"] != expected_entry_hash:
            return ChainVerificationReport(
                ledger_id=ledger_id,
                status="FAIL",
                verified_range={"first": 1 if expected_seq > 1 else 0, "last": expected_seq - 1},
                entries_checked=expected_seq - 1,
                first_broken_sequence=expected_seq,
                expected_hash=expected_entry_hash,
                observed_hash=hdr["entry_hash"],
                reason=f"Canonical SHA-256 hash mismatch at sequence {expected_seq} (journal {jid})",
            )

        expected_prev = expected_entry_hash
        expected_seq += 1

    last_seq = expected_seq - 1
    return ChainVerificationReport(
        ledger_id=ledger_id,
        status="PASS",
        verified_range={"first": 1, "last": last_seq},
        entries_checked=last_seq,
        reason=f"Verified {last_seq} sequential journal entries.",
    )


def create_journal_checkpoint(
    ledger_db_url: str,
    coord_db_url: str,
    ledger_id: str,
    *,
    first_sequence: int = 1,
) -> CheckpointAttestationResult:
    """Compute a Merkle checkpoint over [first_sequence..last] and attest it in Coordinator DB."""
    with get_db_connection(ledger_db_url) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT sequence_number, entry_hash
                FROM journal_headers
                WHERE sequence_number >= %s
                ORDER BY sequence_number ASC;
                """,
                (first_sequence,),
            )
            rows = cur.fetchall()
            if not rows:
                raise ValueError(f"No journal entries found on {ledger_id} from sequence {first_sequence}")
            first_seq = int(rows[0]["sequence_number"])
            last_seq = int(rows[-1]["sequence_number"])
            hashes = [str(r["entry_hash"]) for r in rows]
            merkle_root = compute_merkle_root(hashes)
            cp_id = uuid4()
            cur.execute(
                """
                INSERT INTO journal_checkpoints (
                    checkpoint_id, ledger_id, first_sequence, last_sequence,
                    merkle_root, leaf_count, schema_version
                ) VALUES (%s, %s, %s, %s, %s, %s, 1);
                """,
                (cp_id, ledger_id, first_seq, last_seq, merkle_root, len(hashes)),
            )
        conn.commit()

    with get_db_connection(coord_db_url) as cconn:
        with cconn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO journal_checkpoint_attestations (
                    ledger_id, checkpoint_id, first_sequence, last_sequence,
                    merkle_root, leaf_count, schema_version
                ) VALUES (%s, %s, %s, %s, %s, %s, 1)
                ON CONFLICT (ledger_id, checkpoint_id) DO NOTHING;
                """,
                (ledger_id, cp_id, first_seq, last_seq, merkle_root, len(hashes)),
            )
        cconn.commit()

    return CheckpointAttestationResult(
        checkpoint_id=str(cp_id),
        ledger_id=ledger_id,
        first_sequence=first_seq,
        last_sequence=last_seq,
        merkle_root=merkle_root,
        leaf_count=len(hashes),
        attested_in_coordinator=True,
    )


def verify_journal_checkpoint(
    ledger_db_url: str,
    coord_db_url: str,
    ledger_id: str,
    checkpoint_id: str | None = None,
) -> CheckpointVerificationReport:
    """Verify a Merkle checkpoint against both ledger journal entries and coordinator attestation."""
    try:
        with get_db_connection(ledger_db_url) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                if checkpoint_id:
                    cur.execute(
                        "SELECT * FROM journal_checkpoints WHERE checkpoint_id = %s;",
                        (UUID(checkpoint_id),),
                    )
                else:
                    cur.execute(
                        "SELECT * FROM journal_checkpoints WHERE ledger_id = %s ORDER BY created_at DESC LIMIT 1;",
                        (ledger_id,),
                    )
                cp = cur.fetchone()
                if not cp:
                    return CheckpointVerificationReport(
                        ledger_id=ledger_id,
                        status="INCOMPLETE",
                        reason="No checkpoint found for ledger.",
                    )
                cur.execute(
                    """
                    SELECT entry_hash
                    FROM journal_headers
                    WHERE sequence_number BETWEEN %s AND %s
                    ORDER BY sequence_number ASC;
                    """,
                    (cp["first_sequence"], cp["last_sequence"]),
                )
                hashes = [str(r["entry_hash"]) for r in cur.fetchall()]

        with get_db_connection(coord_db_url) as cconn:
            with cconn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT merkle_root
                    FROM journal_checkpoint_attestations
                    WHERE ledger_id = %s AND checkpoint_id = %s;
                    """,
                    (ledger_id, cp["checkpoint_id"]),
                )
                att = cur.fetchone()
    except Exception as exc:
        return CheckpointVerificationReport(
            ledger_id=ledger_id,
            checkpoint_id=checkpoint_id,
            status="INCOMPLETE",
            reason=f"Database unreachable: {exc}",
        )

    recomputed = compute_merkle_root(hashes)
    cp_id_str = str(cp["checkpoint_id"])
    attested_root = str(att["merkle_root"]) if att else None

    if len(hashes) != int(cp["leaf_count"]) or recomputed != str(cp["merkle_root"]):
        return CheckpointVerificationReport(
            ledger_id=ledger_id,
            checkpoint_id=cp_id_str,
            status="FAIL",
            verified_range={"first": int(cp["first_sequence"]), "last": int(cp["last_sequence"])},
            expected_merkle_root=str(cp["merkle_root"]),
            observed_merkle_root=recomputed,
            attested_merkle_root=attested_root,
            affected_checkpoint=cp_id_str,
            reason="Recomputed Merkle root does not match stored checkpoint.",
        )

    if attested_root != recomputed:
        return CheckpointVerificationReport(
            ledger_id=ledger_id,
            checkpoint_id=cp_id_str,
            status="FAIL",
            verified_range={"first": int(cp["first_sequence"]), "last": int(cp["last_sequence"])},
            expected_merkle_root=attested_root,
            observed_merkle_root=recomputed,
            attested_merkle_root=attested_root,
            affected_checkpoint=cp_id_str,
            reason="Merkle root diverges from Coordinator trust-boundary attestation.",
        )

    return CheckpointVerificationReport(
        ledger_id=ledger_id,
        checkpoint_id=cp_id_str,
        status="PASS",
        verified_range={"first": int(cp["first_sequence"]), "last": int(cp["last_sequence"])},
        expected_merkle_root=str(cp["merkle_root"]),
        observed_merkle_root=recomputed,
        attested_merkle_root=attested_root,
        reason="Merkle root and coordinator attestation verified.",
    )


def verify_all_ledgers(
    *,
    coord_db_url: str | None = None,
    ledger1_db_url: str | None = None,
    ledger2_db_url: str | None = None,
) -> dict[str, Any]:
    """Verify hash chains across Ledger 1 and Ledger 2."""
    l1 = verify_journal_chain(ledger1_db_url or settings.ledger1_db_url, "ledger-1")
    l2 = verify_journal_chain(ledger2_db_url or settings.ledger2_db_url, "ledger-2")
    overall = (
        "INCOMPLETE"
        if "INCOMPLETE" in (l1.status, l2.status)
        else ("FAIL" if "FAIL" in (l1.status, l2.status) else "PASS")
    )
    return {
        "status": overall,
        "ledgers": {
            "ledger-1": l1.model_dump(),
            "ledger-2": l2.model_dump(),
        },
    }
