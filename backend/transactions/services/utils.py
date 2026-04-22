"""Utility functions and constants for the transaction service layer.

Includes validation constants, computation helpers, and reusable ORM
expression builders. No direct database access — ORM expressions are
returned as objects and only execute when evaluated by a queryset.
"""

from decimal import Decimal
from typing import Any

from django.db.models import DecimalField, F, Sum, Value
from django.db.models.expressions import RowRange, Window
from django.db.models.functions import Coalesce

# Valid transaction types — validated in service layer
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


def running_balance_annotation() -> "Coalesce":
    """ORM expression for per-account running balance via window function.

    Subtracts the cumulative sum of balance_deltas (for all preceding rows in
    reverse-date order, per account) from the account's current_balance.
    Reuse: .annotate(running_balance=running_balance_annotation())
    """
    return F("account__current_balance") - Coalesce(  # type: ignore[return-value]
        Window(
            expression=Sum("balance_delta"),
            partition_by=[F("account_id")],
            order_by=[F("date").desc(), F("created_at").desc()],
            frame=RowRange(start=None, end=-1),
        ),
        Value(Decimal("0")),
        output_field=DecimalField(),
    )


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
