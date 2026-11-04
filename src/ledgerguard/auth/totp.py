"""RFC 6238 Time-Based One-Time Password (TOTP) implementation.

Standard RFC 6238 compliant using HMAC-SHA1 with 30-second time steps and 6-digit codes.
Implements secret generation, code derivation, windowed drift verification, and otpauth URI formatting.
"""

import base64
import hashlib
import hmac
import secrets
import struct
import time
import urllib.parse


def generate_totp_secret(length: int = 20) -> str:
    """Generate a random base32-encoded TOTP secret key."""
    random_bytes = secrets.token_bytes(length)
    return base64.b32encode(random_bytes).decode("ascii")


def get_totp_code(secret_b32: str, t: int | None = None, step: int = 30) -> str:
    """Generate a 6-digit TOTP code for the given secret at time t (defaults to now)."""
    if t is None:
        t = int(time.time())
    counter = t // step
    key = base64.b32decode(secret_b32.strip().upper(), casefold=True)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[19] & 0x0F
    code_int = (struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF) % 1000000
    return f"{code_int:06d}"


def verify_totp_code(
    secret_b32: str,
    code: str,
    t: int | None = None,
    step: int = 30,
    drift: int = 1,
) -> bool:
    """Verify a 6-digit TOTP code with time-step drift tolerance (default +-1 step = +-30s)."""
    clean_code = code.strip()
    if len(clean_code) != 6 or not clean_code.isdigit():
        return False

    if t is None:
        t = int(time.time())

    current_step = t // step
    for delta in range(-drift, drift + 1):
        step_time = (current_step + delta) * step
        expected_code = get_totp_code(secret_b32, t=step_time, step=step)
        if secrets.compare_digest(expected_code, clean_code):
            return True
    return False


def get_totp_uri(
    secret_b32: str,
    account_name: str,
    issuer: str = "LedgerGuard",
) -> str:
    """Format an RFC-standard otpauth URI for QR codes or authenticator app imports."""
    encoded_account = urllib.parse.quote(account_name)
    encoded_issuer = urllib.parse.quote(issuer)
    label = f"{encoded_issuer}:{encoded_account}"
    return (
        f"otpauth://totp/{label}"
        f"?secret={secret_b32.strip().upper()}&issuer={encoded_issuer}&algorithm=SHA1&digits=6&period=30"
    )
