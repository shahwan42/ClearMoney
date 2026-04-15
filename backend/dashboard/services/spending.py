"""Dashboard spending — month-over-month comparison, top categories, velocity."""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from django.db.models import CharField, F, Q, Sum, Value
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Coalesce

from core.dates import next_month_range, prev_month_range
from transactions.models import Transaction

if TYPE_CHECKING:
    from . import DashboardData


@dataclass
class CurrencySpending:
    """Per-currency month-over-month spending comparison."""

    currency: str
    this_month: float
    last_month: float
    change: float  # % change (positive = spending more)
    top_categories: list[dict[str, Any]]
    this_month_label: str = ""  # e.g. "Mar 1–25"
    last_month_label: str = ""  # e.g. "Feb"


@dataclass
class SpendingVelocity:
    """Spending pace relative to last month."""

    percentage: float  # current spend / last month total x 100
    days_elapsed: int
    days_total: int
    days_left: int
    day_progress: float  # % of month elapsed
    status: str  # "green", "amber", "red"


def compute_spending_comparison(
    user_id: str, data: DashboardData, tz: ZoneInfo
) -> None:
    """Compute this month vs last month spending + top categories + velocity."""
    now = datetime.now(tz)
    today = now.date()
    this_month_start = today.replace(day=1)
    last_month_start, _ = prev_month_range(today)
    _, next_month_start = next_month_range(today)

    # Spending per currency this month
    this_month_by_currency = _query_spending_by_currency(
        user_id, this_month_start, next_month_start
    )

    # Spending per currency last month
    last_month_by_currency = _query_spending_by_currency(
        user_id, last_month_start, this_month_start
    )

    # Collect all currencies, EGP first
    currencies = set(this_month_by_currency.keys()) | set(last_month_by_currency.keys())
    ordered: list[str] = []
    if "EGP" in currencies:
        ordered.append("EGP")
    for c in sorted(currencies):
        if c != "EGP":
            ordered.append(c)

    # Human-readable date range labels
    month_abbrs = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]
    this_month_label = f"{month_abbrs[this_month_start.month - 1]} 1\u2013{today.day}"
    last_month_label = month_abbrs[last_month_start.month - 1]

    for cur in ordered:
        this_amt = this_month_by_currency.get(cur, 0.0)
        last_amt = last_month_by_currency.get(cur, 0.0)
        change = ((this_amt - last_amt) / last_amt * 100) if last_amt > 0 else 0.0

        top_cats = _query_top_categories(
            user_id, cur, this_month_start, next_month_start, last_month_start
        )

        data.spending_by_currency.append(
            CurrencySpending(
                currency=cur,
                this_month=this_amt,
                last_month=last_amt,
                change=change,
                top_categories=top_cats,
                this_month_label=this_month_label,
                last_month_label=last_month_label,
            )
        )

    # Spending velocity
    _, days_in_month = monthrange(today.year, today.month)
    days_elapsed = today.day
    days_left = days_in_month - days_elapsed
    day_progress = days_elapsed / days_in_month * 100

    total_this = 0.0
    total_last = 0.0
    for cs in data.spending_by_currency:
        rate = (
            data.exchange_rate
            if cs.currency == "USD" and data.exchange_rate > 0
            else 1.0
        )
        total_this += cs.this_month * rate
        total_last += cs.last_month * rate

    pct = (total_this / total_last * 100) if total_last > 0 else 0.0

    if pct <= day_progress:
        status = "green"
    elif pct <= day_progress + 10:
        status = "amber"
    else:
        status = "red"

    data.spending_velocity = SpendingVelocity(
        percentage=pct,
        days_elapsed=days_elapsed,
        days_total=days_in_month,
        days_left=days_left,
        day_progress=day_progress,
        status=status,
    )


def _query_spending_by_currency(
    user_id: str, start: date, end: date
) -> dict[str, float]:
    """Query total expense spending grouped by currency for a date range."""
    rows = (
        Transaction.objects.for_user(user_id)
        .filter(type="expense", date__gte=start, date__lt=end)
        .values("currency")
        .annotate(total=Coalesce(Sum("amount"), Decimal(0)))
        .order_by("currency")
    )
    return {row["currency"]: float(row["total"]) for row in rows}


def _query_top_categories(
    user_id: str,
    currency: str,
    this_month_start: date,
    next_month_start: date,
    last_month_start: date,
) -> list[dict[str, Any]]:
    """Query top 3 spending categories with month-over-month change.

    Two ORM queries + Python merge replace the original CTE:
    1. Top 3 categories this month (with icon).
    2. Last month amounts for those same categories (matched by name).
    NULL categories are surfaced as 'Uncategorized' via Coalesce.
    """
    # Query 1: top 3 expense categories this month
    this_month_rows = list(
        Transaction.objects.filter(
            user_id=user_id,
            type="expense",
            currency=currency,
            date__gte=this_month_start,
            date__lt=next_month_start,
        )
        .values(
            cat_name=Coalesce(
                KeyTextTransform("en", "category__name"),
                Value("Uncategorized"),
                output_field=CharField(),
            ),
            cat_icon=Coalesce(F("category__icon"), Value("")),
        )
        .annotate(amount=Sum("amount"))
        .order_by("-amount")[:3]
    )

    if not this_month_rows:
        return []

    top_names = [r["cat_name"] for r in this_month_rows]

    # Query 2: last month amounts for those categories.
    # 'Uncategorized' maps to NULL category — handle with an OR filter.
    non_null_names = [n for n in top_names if n != "Uncategorized"]
    # Q() is falsy — OR-ing with another Q collapses to that Q (Django Q._combine shortcut)
    last_month_filter = (
        Q(category__name__en__in=non_null_names) if non_null_names else Q()
    )
    if "Uncategorized" in top_names:
        last_month_filter |= Q(category__isnull=True)

    last_month_dict: dict[str, float] = {}
    if last_month_filter:
        for row in (
            Transaction.objects.filter(
                user_id=user_id,
                type="expense",
                currency=currency,
                date__gte=last_month_start,
                date__lt=this_month_start,
            )
            .filter(last_month_filter)
            .values(
                cat_name=Coalesce(
                    KeyTextTransform("en", "category__name"),
                    Value("Uncategorized"),
                    output_field=CharField(),
                )
            )
            .annotate(amount=Sum("amount"))
        ):
            last_month_dict[row["cat_name"]] = float(row["amount"])

    categories: list[dict[str, Any]] = []
    for row in this_month_rows:
        this_f = float(row["amount"])
        last_f = last_month_dict.get(row["cat_name"], 0.0)
        change = ((this_f - last_f) / last_f * 100) if last_f > 0 else 0.0
        categories.append(
            {
                "name": row["cat_name"],
                "icon": row["cat_icon"],
                "amount": this_f,
                "change": change,
                "is_up": change > 0,
            }
        )
    return categories
