"""Transaction activity — recent transactions and streak tracking.

Extracted from dashboard/services/activity.py. These are transaction-domain
concepts that dashboard (and potentially other modules) can import.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.db.models import Count, F

from transactions.models import Transaction

from .utils import running_balance_annotation


@dataclass
class TransactionRow:
    """Recent transaction display row with running balance."""

    id: str
    type: str
    amount: float
    currency: str
    date: date
    note: str | None
    balance_delta: float
    account_name: str
    running_balance: float
    category_name: str | None = None
    category_icon: str | None = None


@dataclass
class StreakInfo:
    """Habit tracking — consecutive days with transactions."""

    consecutive_days: int = 0
    weekly_count: int = 0
    active_today: bool = False


def load_recent_transactions(user_id: str, limit: int = 10) -> list[TransactionRow]:
    """Load recent transactions with running balance.

    Window function computes running balance per account by subtracting the
    cumulative sum of balance_deltas (for preceding rows in reverse-date order)
    from the account's current_balance. No post-window filtering — just ORDER + LIMIT.
    """
    qs = (
        Transaction.objects.filter(user_id=user_id, account__isnull=False)
        .select_related("account", "category")
        .annotate(
            account_name=F("account__name"),
            running_balance=running_balance_annotation(),
        )
        .order_by("-date", "-id")[:limit]
    )

    return [
        TransactionRow(
            id=str(t.id),
            type=t.type,
            amount=float(t.amount),
            currency=t.currency,
            date=t.date,
            note=t.note,
            balance_delta=float(t.balance_delta),
            account_name=t.account_name,
            running_balance=float(t.running_balance),
            category_name=t.category.get_display_name() if t.category else None,
            category_icon=t.category.icon if t.category else None,
        )
        for t in qs
    ]


def load_streak(user_id: str, tz: ZoneInfo) -> StreakInfo:
    """Compute consecutive days with transactions + weekly count.

    Uses a backward-walking algorithm over the last 365 days.
    """
    info = StreakInfo()
    now = datetime.now(tz)
    today = now.date()

    # Distinct transaction dates via GROUP BY + Count, ordered descending.
    # The Count annotation forces grouping so .values_list returns unique dates.
    dates = list(
        Transaction.objects.for_user(user_id)
        .filter(date__lte=today)
        .values("date")
        .annotate(cnt=Count("id"))
        .order_by("-date")
        .values_list("date", flat=True)[:365]
    )

    if not dates:
        return info

    expected = today
    for d in dates:
        if d == expected:
            info.consecutive_days += 1
            if expected == today:
                info.active_today = True
            expected -= timedelta(days=1)
        elif d < expected:
            # Grace period: if no tx today but yesterday has one
            if info.consecutive_days == 0 and d == today - timedelta(days=1):
                info.consecutive_days += 1
                expected = d - timedelta(days=1)
            else:
                break

    # Weekly count (Mon-Sun)
    weekday = now.weekday()  # 0=Mon, 6=Sun
    monday = today - timedelta(days=weekday)
    info.weekly_count = (
        Transaction.objects.for_user(user_id)
        .filter(date__gte=monday, date__lte=today)
        .count()
    )

    return info
