"""
Credit card billing cycle utilities — shared by dashboard and accounts apps.

Extracted here to avoid duplication between dashboard/services.py and
accounts/services.py. Pure functions with no database access, just date math.
Like a Laravel trait or a shared helper in app/Support/.
"""

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any


@dataclass
class BillingCycleInfo:
    """Computed billing cycle info for a credit card."""

    statement_day: int
    due_day: int
    period_start: date
    period_end: date
    due_date: date
    days_until_due: int
    is_due_soon: bool  # true if due within 7 days


def parse_billing_cycle(metadata: dict[str, Any] | None) -> tuple[int, int] | None:
    """Extract (statement_day, due_day) from account metadata JSON.

    Returns None if no billing cycle configured.
    """
    if not metadata:
        return None
    statement_day = metadata.get("statement_day", 0)
    due_day = metadata.get("due_day", 0)
    if not statement_day or not due_day:
        return None
    return (int(statement_day), int(due_day))


def compute_due_date(statement_day: int, due_day: int, today: date) -> date:
    """Compute credit card due date from billing cycle metadata.

    Simplified to just return the due date. Used by dashboard for CC summary cards.
    """
    year = today.year
    month = today.month

    if today.day <= statement_day:
        period_end_month = month
        period_end_year = year
    else:
        period_end_month = month + 1
        period_end_year = year
        if period_end_month > 12:
            period_end_month = 1
            period_end_year += 1

    if due_day > statement_day:
        return date(period_end_year, period_end_month, due_day)
    else:
        due_month = period_end_month + 1
        due_year = period_end_year
        if due_month > 12:
            due_month = 1
            due_year += 1
        return date(due_year, due_month, due_day)


def get_billing_cycle_info(
    statement_day: int, due_day: int, today: date
) -> BillingCycleInfo:
    """Full billing cycle info: period start/end, due date, urgency.

    Uses calendar date arithmetic with explicit month overflow wrapping.

    MONTH OVERFLOW STRATEGY:
    - If statement_day=31 but we're in February, use Feb 28 instead (clamping via monthrange).
    - This preserves the semantic intent: "statement on the 31st → Feb 28" rather than rolling
      forward to Mar 3.
    - Example: Today=Feb 5, statement_day=31 → period_start=Jan 31, period_end=Feb 28.
    """
    year = today.year
    month = today.month
    day = today.day

    if day <= statement_day:
        # CASE 1: day <= statement_day (e.g., today=Mar 15, statement_day=31)
        # → Still in the current billing cycle that started last month
        prev_month = month - 1
        prev_year = year
        if prev_month < 1:
            prev_month = 12
            prev_year -= 1
        # Period started: day AFTER previous month's statement (statement_day+1 of prev_month)
        # Clamp to valid day (e.g., Jan 32 → Jan 31)
        _, max_day = monthrange(prev_year, prev_month)
        start_day = min(statement_day + 1, max_day)
        period_start = date(prev_year, prev_month, start_day)
        # Period ends: on the statement day of the current month
        # Clamp to valid day (e.g., Feb 31 → Feb 28)
        _, max_day_cur = monthrange(year, month)
        period_end = date(year, month, min(statement_day, max_day_cur))
    else:
        # CASE 2: day > statement_day (e.g., today=Mar 31, statement_day=15)
        # → Now in a new billing cycle that started this month
        _, max_day_cur = monthrange(year, month)
        # Period started: day AFTER statement day of current month
        start_day = min(statement_day + 1, max_day_cur)
        period_start = date(year, month, start_day)
        # Period ends: on the statement day of next month
        next_month = month + 1
        next_year = year
        if next_month > 12:
            next_month = 1
            next_year += 1
        _, max_day_next = monthrange(next_year, next_month)
        period_end = date(next_year, next_month, min(statement_day, max_day_next))

    # Due date: computed from period_end, using same logic as compute_due_date
    # If due_day > statement_day, due date is in the same month as period_end.
    # Otherwise, due date is in the next month (payment grace period).
    pe_year = period_end.year
    pe_month = period_end.month
    if due_day > statement_day:
        due_date = date(pe_year, pe_month, due_day)
    else:
        due_month = pe_month + 1
        due_year = pe_year
        if due_month > 12:
            due_month = 1
            due_year += 1
        due_date = date(due_year, due_month, due_day)

    days_until_due = (due_date - today).days
    is_due_soon = 0 <= days_until_due <= 7

    return BillingCycleInfo(
        statement_day=statement_day,
        due_day=due_day,
        period_start=period_start,
        period_end=period_end,
        due_date=due_date,
        days_until_due=days_until_due,
        is_due_soon=is_due_soon,
    )


def get_credit_card_utilization(balance: float, credit_limit: float | None) -> float:
    """Returns 0-100 percentage. Formula: (|balance| / limit) * 100.

    Balance is negative for CC (debt).
    """
    if credit_limit is None or credit_limit <= 0:
        return 0.0
    used = -balance  # balance is negative for CC
    if used <= 0:
        return 0.0
    return used / credit_limit * 100


def interest_free_remaining(
    period_end: date, today: date, total_days: int = 55
) -> tuple[int, bool]:
    """Compute interest-free period remaining days and urgency.

    Returns (days_remaining, is_urgent).
    """
    interest_free_end = period_end + timedelta(days=total_days)
    remaining = (interest_free_end - today).days
    if remaining < 0:
        remaining = 0
    is_urgent = 0 < remaining <= 7
    return remaining, is_urgent
