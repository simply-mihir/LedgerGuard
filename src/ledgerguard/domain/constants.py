"""System constants for well-known accounts and protocols."""

from uuid import UUID

# Well-known system accounts present on every ledger
SYSTEM_CASH_ACCOUNT_ID = UUID("00000000-0000-0000-0000-000000000001")
SYSTEM_CLEARING_ACCOUNT_ID = UUID("00000000-0000-0000-0000-000000000002")

# Default currency
DEFAULT_CURRENCY = "INR"
