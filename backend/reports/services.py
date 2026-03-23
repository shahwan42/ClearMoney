"""Reports service — monthly spending and income aggregation.

Extracted from reports/views.py. Contains all query logic and chart
data building for the monthly reports page.
"""

import logging
from datetime import date
from decimal import Decimal
from typing import Any

from django.db.models import Q, Sum
from django.db.models.functions import Coalesce

from core.models import Transaction
from core.timing import timed

logger = logging.getLogger(__name__)

# Chart color palette
CHART_PALETTE = [
    "#0d9488",  # teal-600
    "#dc2626",  # red-600
    "#2563eb",  # blue-600
    "#d97706",  # amber-600
    "#7c3aed",  # violet-600
    "#059669",  # emerald-600
    "#db2777",  # pink-600
    "#4f46e5",  # indigo-600
]


@timed(threshold_ms=500)
def get_monthly_report(
    user_id: str, year: int, month: int, account_id: str = "", currency: str = ""
) -> dict[str, Any]:
    """Build the full report data for a given month.

    Aggregates spending by category, month summaries, chart segments, and bar data.
    """
    spending, total_spending = get_spending_by_category(
        user_id, year, month, account_id, currency
    )
    chart_segments = build_chart_segments(spending, total_spending)

    current = get_month_summary(user_id, year, month, account_id, currency)

    # Previous month (for comparison)
    prev_year, prev_month = year, month - 1
    if prev_month == 0:
        prev_month = 12
        prev_year -= 1
    previous = get_month_summary(user_id, prev_year, prev_month, account_id, currency)

    # Next month
    next_year, next_month = year, month + 1
    if next_month > 12:
        next_month = 1
        next_year += 1
    next_sum = get_month_summary(user_id, next_year, next_month, account_id, currency)

    # 6-month history for bar chart
    monthly_history = get_monthly_history(user_id, year, month, account_id, currency)
    bar_groups, bar_legend = build_bar_chart(monthly_history)

    month_name = date(year, month, 1).strftime("%B")

    return {
        "year": year,
        "month": month,
        "month_name": month_name,
        "filter_currency": currency,
        "filter_account_id": account_id,
        "spending_by_category": spending,
        "total_spending": total_spending,
        "chart_segments": chart_segments,
        "current_month": current,
        "previous_month": previous,
        "next_month": next_sum,
        "monthly_history": monthly_history,
        "bar_groups": bar_groups,
        "bar_legend": bar_legend,
    }


def get_spending_by_category(
    user_id: str, year: int, month: int, account_id: str = "", currency: str = ""
) -> tuple[list[dict[str, Any]], float]:
    """Get expense totals grouped by category for a month."""
    start_date = date(year, month, 1)
    end_date = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)

    qs = Transaction.objects.for_user(user_id).filter(
        type="expense",
        date__gte=start_date,
        date__lt=end_date,
    )

    if account_id:
        qs = qs.filter(account_id=account_id)
    if currency:
        qs = qs.filter(currency=currency)

    # LEFT JOIN via category FK — NULL category becomes "Uncategorized"
    rows = (
        qs.values("category_id", "category__name", "category__icon")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )

    spending: list[dict[str, Any]] = []
    total = 0.0
    for row in rows:
        amount = float(row["total"])
        total += amount
        spending.append(
            {
                "category_id": str(row["category_id"]) if row["category_id"] else "",
                "name": row["category__name"] or "Uncategorized",
                "icon": row["category__icon"] or "",
                "amount": amount,
                "percentage": 0.0,
            }
        )

    if total > 0:
        for item in spending:
            item["percentage"] = (item["amount"] / total) * 100

    return spending, total


def get_month_summary(
    user_id: str, year: int, month: int, account_id: str = "", currency: str = ""
) -> dict[str, Any]:
    """Get income and expense totals for a single month."""
    start_date = date(year, month, 1)
    end_date = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)

    qs = Transaction.objects.for_user(user_id).filter(
        date__gte=start_date,
        date__lt=end_date,
    )

    if account_id:
        qs = qs.filter(account_id=account_id)
    if currency:
        qs = qs.filter(currency=currency)

    # Conditional aggregation — Sum with filter=Q() computes income and expenses
    # in a single query instead of two separate filtered queries
    result = qs.aggregate(
        income=Coalesce(Sum("amount", filter=Q(type="income")), Decimal(0)),
        expenses=Coalesce(Sum("amount", filter=Q(type="expense")), Decimal(0)),
    )

    income = float(result["income"])
    expenses = float(result["expenses"])
    month_name = date(year, month, 1).strftime("%B")

    return {
        "year": year,
        "month": month,
        "month_name": month_name,
        "income": income,
        "expenses": expenses,
        "net": income - expenses,
    }


def get_monthly_history(
    user_id: str, year: int, month: int, account_id: str = "", currency: str = ""
) -> list[dict[str, Any]]:
    """Get income/expenses for the last 6 months (for the bar chart)."""
    history = []
    for i in range(5, -1, -1):
        m = month - i
        y = year
        while m <= 0:
            m += 12
            y -= 1
        summary = get_month_summary(user_id, y, m, account_id, currency)
        history.append(summary)
    return history


def build_chart_segments(
    spending: list[dict[str, Any]], total: float
) -> list[dict[str, Any]]:
    """Convert category spending into donut chart segments."""
    if total == 0 or not spending:
        return []

    return [
        {
            "label": item["name"],
            "amount": item["amount"],
            "percentage": item["percentage"],
            "color": CHART_PALETTE[i % len(CHART_PALETTE)],
        }
        for i, item in enumerate(spending)
    ]


def build_bar_chart(
    history: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Convert monthly history into bar chart groups with normalized heights."""
    if not history:
        return [], []

    max_val = 0.0
    for m in history:
        max_val = max(max_val, m["income"], m["expenses"])

    groups = []
    for m in history:
        income_h = (m["income"] / max_val * 100) if max_val > 0 else 0
        expense_h = (m["expenses"] / max_val * 100) if max_val > 0 else 0
        label = date(m["year"], m["month"], 1).strftime("%b")
        groups.append(
            {
                "label": label,
                "bars": [
                    {
                        "value": m["income"],
                        "height_pct": income_h,
                        "color": "#059669",
                        "label": "Income",
                    },
                    {
                        "value": m["expenses"],
                        "height_pct": expense_h,
                        "color": "#dc2626",
                        "label": "Expenses",
                    },
                ],
            }
        )

    legend = [
        {"label": "Income", "color": "#059669"},
        {"label": "Expenses", "color": "#dc2626"},
    ]

    return groups, legend
