"""Monetary arithmetic value objects enforcing integer paise and INR currency."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema

# Maximum allowed transaction amount: INR 1 billion (100 billion paise)
MAX_PAISE_AMOUNT = 100_000_000_000  # 1,000,000,000.00 INR
MIN_PAISE_AMOUNT = 1  # 0.01 INR (1 paisa)
SUPPORTED_CURRENCY = "INR"


class AmountPaise:
    """Represents an exact monetary amount in integer paise (1 INR = 100 paise).

    Prevents floating-point precision loss and enforces strict bounds.
    """

    __slots__ = ("_paise",)
    _paise: int

    def __init__(self, value: int | str | AmountPaise):
        if isinstance(value, AmountPaise):
            self._paise = value._paise
            return

        if isinstance(value, float):
            raise TypeError(
                "Floating-point amounts are strictly prohibited; provide integer paise or exact decimal string."
            )

        if isinstance(value, str):
            val_str = value.strip()
            # Allow clean integer strings e.g. "10050" or decimal strings e.g. "100.50"
            if "." in val_str:
                parts = val_str.split(".")
                if len(parts) != 2 or len(parts[1]) > 2:
                    raise ValueError(
                        f"Invalid monetary format '{value}'. At most 2 decimal places allowed."
                    )
                int_part = int(parts[0]) if parts[0] else 0
                frac_part = int(parts[1].ljust(2, "0"))
                int_paise = int_part * 100 + (frac_part if int_part >= 0 else -frac_part)
            else:
                int_paise = int(val_str)
        elif isinstance(value, int):
            # Booleans are subclasses of int in Python; reject them
            if isinstance(value, bool):
                raise TypeError("Boolean value cannot represent an amount.")
            int_paise = value
        else:
            raise TypeError(f"Unsupported amount type {type(value).__name__}; expected int or str.")

        if int_paise < MIN_PAISE_AMOUNT:
            raise ValueError(
                f"Amount must be positive (>= {MIN_PAISE_AMOUNT} paise), got {int_paise}."
            )
        if int_paise > MAX_PAISE_AMOUNT:
            raise ValueError(
                f"Amount exceeds maximum allowed bound of {MAX_PAISE_AMOUNT} paise ({int_paise})."
            )

        self._paise = int_paise

    @property
    def paise(self) -> int:
        """Raw amount in paise (integer)."""
        return self._paise

    @property
    def inr_decimal_str(self) -> str:
        """Formatted INR decimal representation, e.g. '125.50'."""
        rupees = self._paise // 100
        paise = self._paise % 100
        return f"{rupees}.{paise:02d}"

    def __int__(self) -> int:
        return self._paise

    def __repr__(self) -> str:
        return f"AmountPaise({self._paise})"

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, AmountPaise):
            return self._paise == other._paise
        if isinstance(other, int) and not isinstance(other, bool):
            return self._paise == other
        return False

    def __lt__(self, other: Any) -> bool:
        if isinstance(other, AmountPaise):
            return self._paise < other._paise
        if isinstance(other, int) and not isinstance(other, bool):
            return self._paise < other
        return NotImplemented

    def __le__(self, other: Any) -> bool:
        if isinstance(other, AmountPaise):
            return self._paise <= other._paise
        if isinstance(other, int) and not isinstance(other, bool):
            return self._paise <= other
        return NotImplemented

    def __gt__(self, other: Any) -> bool:
        if isinstance(other, AmountPaise):
            return self._paise > other._paise
        if isinstance(other, int) and not isinstance(other, bool):
            return self._paise > other
        return NotImplemented

    def __ge__(self, other: Any) -> bool:
        if isinstance(other, AmountPaise):
            return self._paise >= other._paise
        if isinstance(other, int) and not isinstance(other, bool):
            return self._paise >= other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._paise)

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        def validate_paise(val: Any) -> AmountPaise:
            return AmountPaise(val)

        return core_schema.chain_schema(
            [
                core_schema.union_schema(
                    [
                        core_schema.int_schema(),
                        core_schema.str_schema(),
                        core_schema.is_instance_schema(AmountPaise),
                    ]
                ),
                core_schema.no_info_plain_validator_function(validate_paise),
            ],
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda instance: instance.paise
            ),
        )


# Type alias for Pydantic integration
Paise = Annotated[AmountPaise, AmountPaise]
