"""
Reports views — Django equivalent of Go's Reports handler and ReportsService.

Migrated from:
- internal/handler/pages.go:1973 (Reports handler)
- internal/service/reports.go (ReportsService — SQL aggregation + chart data)

Uses raw SQL via connection.cursor() to match Go's direct DB queries.
The ORM is not used here because these are complex aggregate queries with
GROUP BY, COALESCE, and conditional SUM that don't fit repository patterns.

Like Laravel's DB::raw() or Django's connection.cursor() for reporting.
"""

import logging
from datetime import date
from typing import Any

from django.db import connection
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from core.ratelimit import general_rate
from core.timing import timed
from core.types import AuthenticatedRequest

logger = logging.getLogger(__name__)

# Chart color palette — matches Go's chartPalette in charts.go and reports.go
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


@general_rate
def reports_page(request: AuthenticatedRequest) -> HttpResponse:
    """
    Render the monthly reports page with spending breakdown and income vs expenses.

    GET /reports?year=2026&month=3&currency=EGP&account_id=xxx

    Equivalent of Go's PageHandler.Reports() in pages.go:1973.
    Combines the handler logic (param parsing) and service logic (SQL + chart data)
    from Go's ReportsService.GetMonthlyReport() in reports.go.
    """
    logger.info("page viewed: reports, user=%s", request.user_email)

    user_id = request.user_id
    now = timezone.localtime()
    year = now.year
    month = now.month

    # Parse optional year/month query params (same logic as Go handler)
    year_str = request.GET.get("year", "")
    month_str = request.GET.get("month", "")
    if year_str.isdigit():
        year = int(year_str)
    if month_str.isdigit() and 1 <= int(month_str) <= 12:
        month = int(month_str)

    # Optional filters
    account_id = request.GET.get("account_id", "")
    currency = request.GET.get("currency", "")

    # Build report data (equivalent of ReportsService.GetMonthlyReport)
    report = _get_monthly_report(user_id, year, month, account_id, currency)

    return render(request, "reports/reports.html", {"data": report})


@timed(threshold_ms=500)
def _get_monthly_report(
    user_id: str, year: int, month: int, account_id: str = "", currency: str = ""
) -> dict[str, Any]:
    """
    Build the full report data for a given month.

    Equivalent of Go's ReportsService.GetMonthlyReport() in reports.go:124.
    Aggregates spending by category, month summaries, chart segments, and bar data.

    Args:
        user_id: UUID string of the authenticated user
        year: Report year
        month: Report month (1-12)
        account_id: Optional account filter
        currency: Optional currency filter ('EGP' or 'USD')

    Returns:
        dict with all report data for the template
    """
    # Spending by category for the selected month
    spending, total_spending = _get_spending_by_category(
        user_id,
        year,
        month,
        account_id,
        currency,
    )

    # Build donut chart segments from spending data
    chart_segments = _build_chart_segments(spending, total_spending)

    # Current month summary
    current = _get_month_summary(user_id, year, month, account_id, currency)

    # Previous month (for comparison)
    prev_year, prev_month = year, month - 1
    if prev_month == 0:
        prev_month = 12
        prev_year -= 1
    previous = _get_month_summary(user_id, prev_year, prev_month, account_id, currency)

    # Next month
    next_year, next_month = year, month + 1
    if next_month > 12:
        next_month = 1
        next_year += 1
    next_sum = _get_month_summary(user_id, next_year, next_month, account_id, currency)

    # 6-month history for bar chart
    monthly_history = _get_monthly_history(user_id, year, month, account_id, currency)
    bar_groups, bar_legend = _build_bar_chart(monthly_history)

    # Month name for display
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


def _get_spending_by_category(
    user_id: str, year: int, month: int, account_id: str = "", currency: str = ""
) -> tuple[list[dict[str, Any]], float]:
    """
    Get expense totals grouped by category for a month.

    Equivalent of Go's ReportsService.getSpendingByCategory() in reports.go:276.
    Uses dynamic query building with parameterized placeholders to prevent SQL injection.

    Returns:
        tuple of (list of category dicts, total spending float)
    """
    start_date = date(year, month, 1)
    # End date: first day of next month
    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)

    # Dynamic query building — same pattern as Go's reports.go
    query = """
        SELECT COALESCE(t.category_id::text, ''),
               COALESCE(c.name, 'Uncategorized'),
               COALESCE(c.icon, ''),
               SUM(t.amount)
        FROM transactions t
        LEFT JOIN categories c ON t.category_id = c.id
        WHERE t.type = 'expense' AND t.date >= %s AND t.date < %s AND t.user_id = %s
    """
    params: list[Any] = [start_date, end_date, user_id]

    if account_id:
        query += " AND t.account_id = %s"
        params.append(account_id)
    if currency:
        query += " AND t.currency = %s"
        params.append(currency)

    query += " GROUP BY t.category_id, c.name, c.icon ORDER BY SUM(t.amount) DESC"

    with connection.cursor() as cursor:
        cursor.execute(query, params)
        rows = cursor.fetchall()

    spending = []
    total = 0.0
    for cat_id, name, icon, amount in rows:
        amount = float(amount)
        total += amount
        spending.append(
            {
                "category_id": cat_id,
                "name": name,
                "icon": icon,
                "amount": amount,
                "percentage": 0.0,  # Calculated below
            }
        )

    # Calculate percentages
    if total > 0:
        for item in spending:
            item["percentage"] = (item["amount"] / total) * 100

    return spending, total


def _get_month_summary(
    user_id: str, year: int, month: int, account_id: str = "", currency: str = ""
) -> dict[str, Any]:
    """
    Get income and expense totals for a single month.

    Equivalent of Go's ReportsService.getMonthSummary() in reports.go:328.

    Returns:
        dict with year, month, month_name, income, expenses, net
    """
    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)

    query = """
        SELECT
            COALESCE(SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END), 0),
            COALESCE(SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END), 0)
        FROM transactions
        WHERE date >= %s AND date < %s AND user_id = %s
    """
    params: list[Any] = [start_date, end_date, user_id]

    if account_id:
        query += " AND account_id = %s"
        params.append(account_id)
    if currency:
        query += " AND currency = %s"
        params.append(currency)

    with connection.cursor() as cursor:
        cursor.execute(query, params)
        row = cursor.fetchone()

    income = float(row[0])
    expenses = float(row[1])
    month_name = date(year, month, 1).strftime("%B")

    return {
        "year": year,
        "month": month,
        "month_name": month_name,
        "income": income,
        "expenses": expenses,
        "net": income - expenses,
    }


def _get_monthly_history(
    user_id: str, year: int, month: int, account_id: str = "", currency: str = ""
) -> list[dict[str, Any]]:
    """
    Get income/expenses for the last 6 months (for the bar chart).

    Equivalent of Go's ReportsService.getMonthlyHistory() in reports.go:247.
    Walks backward from the current month to build a 6-month trend.
    """
    history = []
    for i in range(5, -1, -1):
        # Walk backward from current month
        m = month - i
        y = year
        while m <= 0:
            m += 12
            y -= 1
        summary = _get_month_summary(user_id, y, m, account_id, currency)
        history.append(summary)
    return history


def _build_chart_segments(
    spending: list[dict[str, Any]], total: float
) -> list[dict[str, Any]]:
    """
    Convert category spending into donut chart segments.

    Equivalent of Go's ReportsService.buildChartSegments() in reports.go:189.
    Each segment gets a color from the 8-color palette.

    Returns:
        list of dicts with 'label', 'amount', 'percentage', 'color' keys
    """
    if total == 0 or not spending:
        return []

    segments = []
    for i, item in enumerate(spending):
        segments.append(
            {
                "label": item["name"],
                "amount": item["amount"],
                "percentage": item["percentage"],
                "color": CHART_PALETTE[i % len(CHART_PALETTE)],
            }
        )
    return segments


def _build_bar_chart(
    history: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Convert monthly history into bar chart groups with normalized heights.

    Equivalent of Go's ReportsService.buildBarChart() in reports.go:206.
    Heights are normalized so the tallest bar is 100%.

    Returns:
        tuple of (list of bar groups, list of legend items)
    """
    if not history:
        return [], []

    # Find max value for height normalization
    max_val = 0.0
    for m in history:
        max_val = max(max_val, m["income"], m["expenses"])

    groups = []
    for m in history:
        income_h = (m["income"] / max_val * 100) if max_val > 0 else 0
        expense_h = (m["expenses"] / max_val * 100) if max_val > 0 else 0
        # Short month name (first 3 chars) — matches Go's m.Month.String()[:3]
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
