"""Dashboard spending — month-over-month comparison, top categories, velocity."""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from django.db import connection
from django.db.models import Sum
from django.db.models.functions import Coalesce

from core.models import Transaction

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

    # Last month start
    if this_month_start.month == 1:
        last_month_start = date(this_month_start.year - 1, 12, 1)
    else:
        last_month_start = date(this_month_start.year, this_month_start.month - 1, 1)

    # Next month start (end of current month range)
    if this_month_start.month == 12:
        next_month_start = date(this_month_start.year + 1, 1, 1)
    else:
        next_month_start = date(this_month_start.year, this_month_start.month + 1, 1)

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

    Raw SQL — CTE joins this month's top 3 with last month's totals for the
    same categories. Cross-period comparison doesn't map cleanly to ORM.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            """
            WITH this_month AS (
                SELECT COALESCE(c.name, 'Uncategorized') AS cat_name,
                    COALESCE(c.icon, '') AS cat_icon,
                    SUM(t.amount) AS amount
                FROM transactions t
                LEFT JOIN categories c ON t.category_id = c.id
                WHERE t.type = 'expense' AND t.currency = %s
                    AND t.date >= %s AND t.date < %s
                    AND t.user_id = %s
                GROUP BY c.name, c.icon
                ORDER BY SUM(t.amount) DESC
                LIMIT 3
            ),
            last_month AS (
                SELECT COALESCE(c.name, 'Uncategorized') AS cat_name,
                    SUM(t.amount) AS amount
                FROM transactions t
                LEFT JOIN categories c ON t.category_id = c.id
                WHERE t.type = 'expense' AND t.currency = %s
                    AND t.date >= %s AND t.date < %s
                    AND t.user_id = %s
                GROUP BY c.name
            )
            SELECT tm.cat_name, tm.cat_icon, tm.amount,
                COALESCE(lm.amount, 0) AS last_amount
            FROM this_month tm
            LEFT JOIN last_month lm ON tm.cat_name = lm.cat_name
            """,
            [
                currency,
                this_month_start,
                next_month_start,
                user_id,
                currency,
                last_month_start,
                this_month_start,
                user_id,
            ],
        )
        rows = cursor.fetchall()

    categories: list[dict[str, Any]] = []
    for name, icon, this_amt, last_amt in rows:
        this_f = float(this_amt)
        last_f = float(last_amt)
        change = ((this_f - last_f) / last_f * 100) if last_f > 0 else 0.0
        categories.append(
            {
                "name": name,
                "icon": icon,
                "amount": this_f,
                "change": change,
                "is_up": change > 0,
            }
        )
    return categories
