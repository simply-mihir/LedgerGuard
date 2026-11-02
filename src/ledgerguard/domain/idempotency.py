"""Idempotency canonical payload fingerprinting and conflict exceptions."""

import hashlib
import json
from typing import Any


class IdempotencyConflictError(Exception):
    """Raised when an idempotency key is reused with a different canonical payload."""

    pass


def canonical_json_dumps(payload: dict[str, Any]) -> str:
    """Format dictionary into deterministic canonical JSON (sorted keys, no extra whitespace)."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def compute_payload_hash(payload: dict[str, Any]) -> str:
    """Compute SHA-256 fingerprint from canonical JSON payload representation."""
    canonical_str = canonical_json_dumps(payload)
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
