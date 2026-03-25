"""Dashboard activity — people summary, streak tracking, recent transactions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from django.db.models import Count, F

from core.models import Person, Transaction
from transactions.services.utils import running_balance_annotation

if TYPE_CHECKING:
    from . import DashboardData


@dataclass
class PeopleCurrencySummary:
    """Per-currency people ledger totals."""

    currency: str
    owed_to_me: float = 0.0
    i_owe: float = 0.0


@dataclass
class StreakInfo:
    """Habit tracking — consecutive days with transactions."""

    consecutive_days: int = 0
    weekly_count: int = 0
    active_today: bool = False


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


def load_people_summary(user_id: str, data: DashboardData) -> None:
    """Load people ledger grouped by currency."""
    rows = (
        Person.objects.for_user(user_id)
        .order_by("name")
        .values_list("name", "net_balance", "net_balance_egp", "net_balance_usd")
    )

    egp = PeopleCurrencySummary(currency="EGP")
    usd = PeopleCurrencySummary(currency="USD")

    for _name, net_balance, net_balance_egp, net_balance_usd in rows:
        nb = float(net_balance)
        nb_egp = float(net_balance_egp)
        nb_usd = float(net_balance_usd)

        if nb_egp > 0:
            egp.owed_to_me += nb_egp
        elif nb_egp < 0:
            egp.i_owe += nb_egp

        if nb_usd > 0:
            usd.owed_to_me += nb_usd
        elif nb_usd < 0:
            usd.i_owe += nb_usd

        if nb > 0:
            data.people_owed_to_me += nb
        elif nb < 0:
            data.people_i_owe += nb

    if egp.owed_to_me != 0 or egp.i_owe != 0:
        data.people_by_currency.append(egp)
    if usd.owed_to_me != 0 or usd.i_owe != 0:
        data.people_by_currency.append(usd)

    data.has_people_activity = (
        len(data.people_by_currency) > 0
        or data.people_owed_to_me != 0
        or data.people_i_owe != 0
    )


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


def load_recent_transactions(user_id: str, limit: int = 10) -> list[TransactionRow]:
    """Load recent transactions with running balance.

    Window function computes running balance per account by subtracting the
    cumulative sum of balance_deltas (for preceding rows in reverse-date order)
    from the account's current_balance. No post-window filtering — just ORDER + LIMIT.
    """
    qs = (
        Transaction.objects.filter(user_id=user_id)
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
            category_name=t.category.name if t.category else None,
            category_icon=t.category.icon if t.category else None,
        )
        for t in qs
    ]
