"""Dashboard spending — month-over-month comparison, top categories, velocity projections.

Velocity projections surface the existing SpendingVelocity computation as actionable
daily budget advice:
  - daily_remaining: how much the user can spend per day to stay on last month's pace
  - projected_total: (spent / elapsed_days) * total_days — estimated month-end spend
  - reduce_by: the daily reduction needed when amber/red
  - Per-category velocity for budgeted categories
"""

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

from budgets.services import BudgetService
from core.dates import next_month_range, prev_month_range
from core.status import compute_spending_velocity_status
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
    """Spending pace relative to last month, with actionable projections.

    Fields
    ------
    percentage       -- current spend / last month total × 100
    days_elapsed     -- calendar days elapsed so far this month
    days_total       -- total calendar days in this month
    days_left        -- remaining calendar days (days_total - days_elapsed)
    day_progress     -- % of month elapsed (days_elapsed / days_total × 100)
    status           -- "green" | "amber" | "red"
    daily_pace       -- current daily spending rate (spent / days_elapsed)
    budget_daily     -- target daily rate to match last month (last_month / days_total)
    daily_remaining  -- how much the user can spend per remaining day and still match
                        budget: (budget_total - spent) / days_left.  Negative means
                        budget already exceeded.
    projected_total  -- estimated full-month spend at current pace:
                        (spent / days_elapsed) * days_total.  0 if days_elapsed == 0.
    budget_total     -- last month's total used as the budget reference
    reduce_by        -- daily reduction needed when over pace:
                        daily_pace - budget_daily.  0 when on track.
    """

    percentage: float
    days_elapsed: int
    days_total: int
    days_left: int
    day_progress: float
    status: str  # "green", "amber", "red"

    # Projection fields (default 0 so callers don't need to pass them)
    daily_pace: float = 0.0
    budget_daily: float = 0.0
    daily_remaining: float = 0.0
    projected_total: float = 0.0
    budget_total: float = 0.0
    reduce_by: float = 0.0


@dataclass
class CategoryVelocity:
    """Per-category spending velocity for a budgeted category.

    Attributes
    ----------
    category_name   -- display name of the category
    category_icon   -- emoji / icon string (may be empty)
    monthly_limit   -- budget limit for this category this month
    spent           -- amount spent so far this month
    currency        -- currency of the budget and spending
    daily_remaining -- (monthly_limit - spent) / days_left; negative if over budget
    projected_total -- (spent / days_elapsed) * days_total at current pace
    percentage      -- spent / monthly_limit × 100
    status          -- "green" | "amber" | "red"
    reduce_by       -- daily reduction needed (max(0, daily_pace - budget_daily))
    """

    category_name: str
    category_icon: str
    monthly_limit: float
    spent: float
    currency: str
    daily_remaining: float = 0.0
    projected_total: float = 0.0
    percentage: float = 0.0
    status: str = "green"
    reduce_by: float = 0.0


def compute_spending_comparison(
    user_id: str, data: DashboardData, tz: ZoneInfo
) -> None:
    """Compute this month vs last month spending + top categories + velocity projections."""
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

    # ---- Spending velocity + projections ----
    _, days_in_month = monthrange(today.year, today.month)
    days_elapsed = today.day
    days_left = days_in_month - days_elapsed
    day_progress = days_elapsed / days_in_month * 100

    # Totals ONLY for selected_currency (no cross-currency conversion)
    selected_cs = next(
        (
            cs
            for cs in data.spending_by_currency
            if cs.currency == data.selected_currency
        ),
        None,
    )
    data.selected_spending = selected_cs
    total_this = selected_cs.this_month if selected_cs else 0.0
    total_last = selected_cs.last_month if selected_cs else 0.0

    pct = (total_this / total_last * 100) if total_last > 0 else 0.0

    status = compute_spending_velocity_status(pct, day_progress)

    # Projection math
    # daily_pace: average daily spend this month (avoid div-by-0 on day 0)
    daily_pace = (total_this / days_elapsed) if days_elapsed > 0 else 0.0

    # budget_daily: what the daily rate should be to match last month exactly
    budget_daily = (total_last / days_in_month) if days_in_month > 0 else 0.0

    # projected_total: extrapolate current pace to end of month
    projected_total = daily_pace * days_in_month

    # daily_remaining: how much budget is left to spread across remaining days
    # When there is no last-month baseline (total_last=0) we have no spending target,
    # so daily_remaining is meaningless — return 0.
    # Negative means budget already blown for the month.
    if total_last <= 0:
        daily_remaining = 0.0
    elif days_left > 0:
        daily_remaining = (total_last - total_this) / days_left
    elif total_last > 0:
        # Last day of the month: show what was available today
        daily_remaining = total_last - total_this
    else:
        daily_remaining = 0.0

    # reduce_by: daily cut needed to get back on track (0 when already on track)
    reduce_by = max(0.0, daily_pace - budget_daily)

    data.spending_velocity = SpendingVelocity(
        percentage=pct,
        days_elapsed=days_elapsed,
        days_total=days_in_month,
        days_left=days_left,
        day_progress=day_progress,
        status=status,
        daily_pace=daily_pace,
        budget_daily=budget_daily,
        daily_remaining=daily_remaining,
        projected_total=projected_total,
        budget_total=total_last,
        reduce_by=reduce_by,
    )


def compute_category_velocities(
    user_id: str, tz: ZoneInfo, selected_currency: str
) -> list[CategoryVelocity]:
    """Compute per-category spending velocity for all active budgets.

    For each active budget:
    - Calculates daily_remaining: how much budget is left to spend per day
    - Calculates projected_total: extrapolated month-end spend at current pace
    - Assigns traffic-light status mirroring the global velocity logic

    Returns an empty list when the user has no active budgets or none matching
    the selected currency.
    """
    today = datetime.now(tz).date()
    _, days_in_month = monthrange(today.year, today.month)
    days_elapsed = today.day
    days_left = days_in_month - days_elapsed

    svc = BudgetService(user_id, tz)
    budgets = svc.get_all_with_spending()

    result: list[CategoryVelocity] = []
    for b in budgets:
        if b.currency != selected_currency:
            continue

        spent = b.spent
        limit = b.effective_limit  # respects rollover

        # Per-category projection math (same formulas as global velocity)
        daily_pace = (spent / days_elapsed) if days_elapsed > 0 else 0.0
        budget_daily = (limit / days_in_month) if days_in_month > 0 else 0.0
        projected_total = daily_pace * days_in_month

        if days_left > 0:
            daily_remaining = (limit - spent) / days_left
        elif limit > 0:
            daily_remaining = limit - spent
        else:
            daily_remaining = 0.0

        reduce_by = max(0.0, daily_pace - budget_daily)

        # Status: compare projected vs limit (traffic-light)
        pct = (spent / limit * 100) if limit > 0 else 0.0
        day_progress = (
            (days_elapsed / days_in_month * 100) if days_in_month > 0 else 0.0
        )
        from core.status import compute_spending_velocity_status as _sv_status

        status = _sv_status(pct, day_progress)

        result.append(
            CategoryVelocity(
                category_name=b.category_name,
                category_icon=b.category_icon,
                monthly_limit=limit,
                spent=spent,
                currency=b.currency,
                daily_remaining=daily_remaining,
                projected_total=projected_total,
                percentage=pct,
                status=status,
                reduce_by=reduce_by,
            )
        )

    return result


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
