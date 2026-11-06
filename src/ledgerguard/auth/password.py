"""Argon2id password hashing and constant-time verification utilities."""

import argon2
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

# Standard Argon2id configuration (RFC 9106 recommended parameters)
_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MiB
    parallelism=4,
    hash_len=32,
    salt_len=16,
    type=argon2.Type.ID,
)

# Precomputed dummy hash for constant-time dummy verification on invalid user lookup
_DUMMY_HASH = _hasher.hash("dummy_constant_time_filler_secret_only")


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id."""
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Verify a plaintext password against an Argon2id hash."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def dummy_verify_password(password: str) -> bool:
    """Perform dummy verification to prevent timing side-channels on missing accounts."""
    try:
        _hasher.verify(_DUMMY_HASH, password)
    except Exception:
        pass
    return False


def needs_rehash(password_hash: str) -> bool:
    """Check if the password hash needs upgrading to newer parameters."""
    try:
        return _hasher.check_needs_rehash(password_hash)
    except Exception:
        return True
