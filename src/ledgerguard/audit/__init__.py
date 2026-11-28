"""Tamper-evident audit journal hash chain and Merkle checkpoint verification."""

from ledgerguard.audit.journal_chain import (
    ChainVerificationReport,
    CheckpointAttestationResult,
    CheckpointVerificationReport,
    compute_entry_hash,
    compute_merkle_root,
    create_journal_checkpoint,
    verify_all_ledgers,
    verify_journal_chain,
    verify_journal_checkpoint,
)

__all__ = [
    "ChainVerificationReport",
    "CheckpointAttestationResult",
    "CheckpointVerificationReport",
    "compute_entry_hash",
    "compute_merkle_root",
    "create_journal_checkpoint",
    "verify_all_ledgers",
    "verify_journal_chain",
    "verify_journal_checkpoint",
]
