"""Reports service — monthly spending and income aggregation.

Extracted from reports/views.py. Contains all query logic and chart
data building for the monthly reports page.
"""

import dataclasses
import logging
from datetime import date
from typing import Any
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta
from django.db.models import Sum
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import ExtractMonth, ExtractYear

from accounts.services import AccountService, compute_net_worth
from core.dates import month_range
from core.monthly import get_month_summary  # re-exported for backward compat
from core.projection import ProjectionService
from core.timing import timed
from transactions.models import Transaction

logger = logging.getLogger(__name__)

# Chart color palette — mirrors core/templatetags/money.py CHART_PALETTE.
# Uses CSS custom properties so dark mode overrides via .dark { --chart-N: ... } in charts.css.
CHART_PALETTE = [
    "var(--chart-1)",  # teal
    "var(--chart-2)",  # red
    "var(--chart-3)",  # blue
    "var(--chart-4)",  # amber
    "var(--chart-5)",  # violet
    "var(--chart-6)",  # emerald
    "var(--chart-7)",  # pink
    "var(--chart-8)",  # indigo
]


@timed(threshold_ms=500)
def get_monthly_report(
    user_id: str,
    year: int,
    month: int,
    account_id: str = "",
    currency: str = "",
    months: int = 6,
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

    # New: Insights and trends
    insights = get_insights(user_id, year, month, account_id, currency, months=months)

    # New: Spending by tag
    tag_spending = get_spending_by_tag(user_id, year, month, account_id, currency)

    # New: Fee analytics
    fees = get_fee_analytics(user_id, year, month, account_id, currency)

    # New: Net worth projection
    proj_svc = ProjectionService(user_id, ZoneInfo("UTC"))

    # Estimate current net worth from latest summaries
    acc_svc = AccountService(user_id, ZoneInfo("UTC"))
    all_accs = acc_svc.get_all()

    # Convert summaries to dicts for compute_net_worth
    acc_dicts = [dataclasses.asdict(a) for a in all_accs]
    nw_summary = compute_net_worth(acc_dicts)
    projection = proj_svc.get_projection(nw_summary.net_worth, months=12)

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
        "insights": insights,
        "trend_period": months,
        "tag_spending": tag_spending,
        "fees": fees,
        "projection": projection,
    }


def get_spending_by_tag(
    user_id: str, year: int, month: int, account_id: str = "", currency: str = ""
) -> list[dict[str, Any]]:
    """Get expense totals grouped by tag for a month."""
    start_date, end_date = month_range(date(year, month, 1))

    qs = Transaction.objects.for_user(user_id).filter(
        type="expense",
        date__gte=start_date,
        date__lt=end_date,
    )

    if account_id:
        qs = qs.filter(account_id=account_id)
    if currency:
        qs = qs.filter(currency=currency)

    # Aggregate by tag name
    rows = qs.values("tags__name").annotate(total=Sum("amount")).order_by("-total")

    tag_spending = []
    for row in rows:
        if row["tags__name"]:
            tag_spending.append(
                {
                    "name": row["tags__name"],
                    "amount": float(row["total"]),
                }
            )

    return tag_spending


def get_insights(
    user_id: str,
    year: int,
    month: int,
    account_id: str = "",
    currency: str = "",
    months: int = 6,
) -> dict[str, Any]:
    """Calculate spending trends, anomalies, and savings rate."""
    category_trends = get_category_trends(
        user_id, year, month, months, account_id, currency
    )
    savings_rate_history = get_savings_rate_history(
        user_id, year, month, months, account_id, currency
    )

    # Identify anomalies and growing categories
    anomalies = []
    growing = []

    for trend in category_trends:
        current_val = trend["current"]
        avg_val = trend["average_3m"]

        # Anomaly: current > 130% of 3-month rolling average (if avg > 0)
        if avg_val > 0 and current_val > (avg_val * 1.3):
            pct_increase = ((current_val - avg_val) / avg_val) * 100
            anomalies.append(
                {
                    "category": trend["name"],
                    "icon": trend["icon"],
                    "pct_increase": round(pct_increase),
                    "current": current_val,
                    "average": avg_val,
                }
            )

        # Growing: current > average
        if current_val > avg_val:
            growing.append(trend)

    # Sort growing by absolute increase
    growing.sort(key=lambda x: x["current"] - x["average_3m"], reverse=True)
    top_growing = growing[:3]

    return {
        "category_trends": category_trends,
        "anomalies": anomalies,
        "top_growing": top_growing,
        "savings_rate_history": savings_rate_history,
        "current_savings_rate": (
            savings_rate_history[-1]["rate"] if savings_rate_history else 0
        ),
    }


def get_category_trends(
    user_id: str,
    year: int,
    month: int,
    months: int = 6,
    account_id: str = "",
    currency: str = "",
) -> list[dict[str, Any]]:
    """Get monthly spending history per category with sparkline values."""
    end_date = month_range(date(year, month, 1))[1]
    start_date = date(year, month, 1) - relativedelta(months=months - 1)

    qs = Transaction.objects.for_user(user_id).filter(
        type="expense",
        date__gte=start_date,
        date__lt=end_date,
    )
    if account_id:
        qs = qs.filter(account_id=account_id)
    if currency:
        qs = qs.filter(currency=currency)

    rows = (
        qs.annotate(
            m=ExtractMonth("date"),
            y=ExtractYear("date"),
            category_name_en=KeyTextTransform("en", "category__name"),
        )
        .values("y", "m", "category_id", "category_name_en", "category__icon")
        .annotate(total=Sum("amount"))
        .order_by("y", "m")
    )

    # Map results: category -> { (y, m) -> total }
    data: dict[tuple[str, str, str], dict[tuple[int, int], float]] = {}
    for row in rows:
        cat_key = (
            str(row["category_id"]) if row["category_id"] else "",
            row["category_name_en"] or "Uncategorized",
            row["category__icon"] or "",
        )
        if cat_key not in data:
            data[cat_key] = {}
        data[cat_key][(row["y"], row["m"])] = float(row["total"])

    # Build history for each category
    trends = []
    months_list = []
    for i in range(months - 1, -1, -1):
        dt = date(year, month, 1) - relativedelta(months=i)
        months_list.append((dt.year, dt.month))

    for cat_key, history in data.items():
        cat_id, name, icon = cat_key
        values = []
        for y, m in months_list:
            values.append(history.get((y, m), 0.0))

        current = values[-1]
        # 3-month rolling average
        last_3 = values[-3:] if len(values) >= 3 else values
        avg_3m = sum(last_3) / len(last_3) if last_3 else 0

        trends.append(
            {
                "category_id": cat_id,
                "name": name,
                "icon": icon,
                "values": values,
                "current": current,
                "average_3m": avg_3m,
            }
        )

    # Sort trends by current month spending
    trends.sort(key=lambda x: float(str(x["current"])), reverse=True)
    return trends


def get_savings_rate_history(
    user_id: str,
    year: int,
    month: int,
    months: int = 6,
    account_id: str = "",
    currency: str = "",
) -> list[dict[str, Any]]:
    """Calculate savings rate (income-expenses)/income for the last N months."""
    history = []
    for i in range(months - 1, -1, -1):
        dt = date(year, month, 1) - relativedelta(months=i)
        summary = get_month_summary(user_id, dt.year, dt.month, account_id, currency)
        income = summary["income"]
        expenses = summary["expenses"]

        rate = 0.0
        if income > 0:
            rate = ((income - expenses) / income) * 100

        history.append(
            {
                "year": dt.year,
                "month": dt.month,
                "label": dt.strftime("%b"),
                "rate": rate,
                "income": income,
                "expenses": expenses,
            }
        )
    return history


def get_spending_by_category(
    user_id: str, year: int, month: int, account_id: str = "", currency: str = ""
) -> tuple[list[dict[str, Any]], float]:
    """Get expense totals grouped by category for a month."""
    start_date, end_date = month_range(date(year, month, 1))

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
        qs.annotate(category_name_en=KeyTextTransform("en", "category__name"))
        .values("category_id", "category_name_en", "category__icon")
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
                "name": row["category_name_en"] or "Uncategorized",
                "icon": row["category__icon"] or "",
                "amount": amount,
                "percentage": 0.0,
            }
        )

    if total > 0:
        for item in spending:
            item["percentage"] = (item["amount"] / total) * 100

    return spending, total


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
                        "color": "var(--chart-income)",
                        "label": "Income",
                    },
                    {
                        "value": m["expenses"],
                        "height_pct": expense_h,
                        "color": "var(--chart-expenses)",
                        "label": "Expenses",
                    },
                ],
            }
        )

    legend = [
        {"label": "Income", "color": "var(--chart-income)"},
        {"label": "Expenses", "color": "var(--chart-expenses)"},
    ]

    return groups, legend


def get_fee_analytics(
    user_id: str, year: int, month: int, account_id: str = "", currency: str = ""
) -> dict[str, Any]:
    """Calculate fee summary, breakdowns and trends."""
    # Base queryset for fees
    base_qs = Transaction.objects.for_user(user_id).filter(
        category__name__en="Fees & Charges"
    )

    if account_id:
        base_qs = base_qs.filter(account_id=account_id)
    if currency:
        base_qs = base_qs.filter(currency=currency)

    # Total this year
    year_total = float(
        base_qs.filter(date__year=year).aggregate(total=Sum("amount"))["total"] or 0
    )

    # Total this month
    month_total = float(
        base_qs.filter(date__year=year, date__month=month).aggregate(
            total=Sum("amount")
        )["total"]
        or 0
    )

    # Breakdown by account (Yearly)
    acc_rows = (
        base_qs.filter(date__year=year)
        .values("account__name")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )
    by_account = [
        {"name": r["account__name"], "amount": float(r["total"])} for r in acc_rows
    ]

    # Breakdown by type (Monthly)
    month_qs = base_qs.filter(date__year=year, date__month=month).select_related(
        "linked_transaction"
    )
    by_type_map = {"transfer": 0.0, "exchange": 0.0, "expense": 0.0, "other": 0.0}

    for tx in month_qs:
        amount = float(tx.amount)
        if tx.linked_transaction:
            t = tx.linked_transaction.type
            # Map system types to user-friendly labels if needed, or just group
            if t in ["transfer", "exchange", "expense"]:
                by_type_map[t] += amount
            else:
                by_type_map["other"] += amount
        else:
            # Fallback to note parsing for unlinked fees (like InstaPay or manual)
            note = (tx.note or "").lower()
            if "instapay" in note or "transfer" in note:
                by_type_map["transfer"] += amount
            elif "exchange" in note:
                by_type_map["exchange"] += amount
            elif "fawry" in note or "cashout" in note:
                by_type_map["expense"] += amount
            else:
                by_type_map["other"] += amount

    by_type = [
        {"name": k.capitalize(), "amount": v} for k, v in by_type_map.items() if v > 0
    ]
    by_type.sort(key=lambda x: x["amount"], reverse=True)

    # Trend (Last 6 months)
    trend = []
    for i in range(5, -1, -1):
        dt = date(year, month, 1) - relativedelta(months=i)
        m_total = float(
            base_qs.filter(date__year=dt.year, date__month=dt.month).aggregate(
                total=Sum("amount")
            )["total"]
            or 0
        )
        trend.append({"label": dt.strftime("%b"), "amount": m_total})

    return {
        "month_total": month_total,
        "year_total": year_total,
        "by_account": by_account,
        "by_type": by_type,
        "trend": trend,
        "currency": currency or "EGP",
    }
