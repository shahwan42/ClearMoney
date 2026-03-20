"""Pure utility functions and constants for the transaction service layer.

No database access, no side effects — just validation constants and
computation helpers used across CRUD, transfer, and helper modules.
"""

from typing import Any

# Valid transaction types — must match PostgreSQL enum
VALID_TX_TYPES = {
    "expense",
    "income",
    "transfer",
    "exchange",
    "loan_out",
    "loan_in",
    "loan_repayment",
}

CREDIT_ACCOUNT_TYPES = {"credit_card", "credit_limit"}


def _to_str(value: Any) -> str | None:
    """Convert to non-empty string, or None."""
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _parse_tags(value: Any) -> list[str]:
    """Parse tags from DB result (may be list, string, or None)."""
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        # PostgreSQL returns text[] as '{tag1,tag2}'
        stripped = value.strip("{}")
        if stripped:
            return [t.strip('"') for t in stripped.split(",")]
    return []


def calculate_instapay_fee(amount: float) -> float:
    """Compute InstaPay fee: 0.1% of amount, min 0.5, max 20 EGP."""
    fee = amount * 0.001
    if fee < 0.5:
        fee = 0.5
    if fee > 20:
        fee = 20
    return round(fee, 2)


def resolve_exchange_fields(
    amount: float | None,
    rate: float | None,
    counter_amount: float | None,
) -> tuple[float, float, float]:
    """Compute the missing field from two provided values.

    Formula: amount * rate = counter_amount
    Raises ValueError if fewer than 2 values are provided.
    """
    count = sum(1 for v in (amount, rate, counter_amount) if v is not None and v > 0)
    if count < 2:
        raise ValueError("Provide at least two of: amount, rate, counter_amount")

    if amount and amount > 0 and rate and rate > 0:
        return amount, rate, round(amount * rate, 2)
    if amount and amount > 0 and counter_amount and counter_amount > 0:
        return amount, round(counter_amount / amount, 6), counter_amount
    if rate and rate > 0 and counter_amount and counter_amount > 0:
        return round(counter_amount / rate, 2), rate, counter_amount

    raise ValueError("Invalid exchange parameters")
