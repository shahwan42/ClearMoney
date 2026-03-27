"""Dashboard widgets — health warnings, budgets, virtual accounts, investments."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from django.db.models import DecimalField, F, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce

from accounts.services import load_health_warnings  # noqa: F401
from accounts.types import HealthWarning  # noqa: F401
from core.models import Budget, Investment, Transaction, VirtualAccount


def load_budgets_with_spending(user_id: str, tz: ZoneInfo) -> list[dict[str, Any]]:
    """Load budgets with current month's actual spending."""
    today = datetime.now(tz).date()
    month_start = today.replace(day=1)
    if today.month == 12:
        month_end = date(today.year + 1, 1, 1)
    else:
        month_end = date(today.year, today.month + 1, 1)

    # Subquery sums expenses for the budget's category+currency+user in the current month.
    # OuterRef('currency') and OuterRef('user_id') match the cross-column conditions from
    # the original LEFT JOIN (t.currency = b.currency AND t.user_id = b.user_id).
    spent_subquery = (
        Transaction.objects.filter(
            category_id=OuterRef("category_id"),
            type="expense",
            date__gte=month_start,
            date__lt=month_end,
            currency=OuterRef("currency"),
            user_id=OuterRef("user_id"),
        )
        .values("category_id")
        .annotate(total=Sum("amount"))
        .values("total")
    )

    budget_qs = (
        Budget.objects.filter(user_id=user_id, is_active=True)
        .select_related("category")
        .annotate(
            spent=Coalesce(
                Subquery(spent_subquery, output_field=DecimalField()),
                Value(Decimal("0")),
            )
        )
        .order_by("category__name")
    )

    budgets: list[dict[str, Any]] = []
    for b in budget_qs:
        limit_amt = float(b.monthly_limit)
        spent = float(b.spent)
        pct = (spent / limit_amt * 100) if limit_amt > 0 else 0.0

        if pct >= 100:
            status = "red"
        elif pct >= 80:
            status = "amber"
        else:
            status = "green"

        budgets.append(
            {
                "id": str(b.id),
                "category_id": str(b.category_id),
                "monthly_limit": limit_amt,
                "currency": b.currency,
                "category_name": b.category.name,
                "category_icon": b.category.icon or "",
                "spent": spent,
                "percentage": pct,
                "status": status,
            }
        )
    return budgets


def load_virtual_accounts(user_id: str) -> list[dict[str, Any]]:
    """Load active virtual accounts for dashboard widget."""
    rows = (
        VirtualAccount.objects.for_user(user_id)
        .filter(is_archived=False)
        .order_by("display_order", "name")
    )

    result: list[dict[str, Any]] = []
    for row in rows:
        target = float(row.target_amount) if row.target_amount else 0.0
        current = float(row.current_balance)
        progress = (current / target * 100) if target > 0 else 0.0
        result.append(
            {
                "id": str(row.id),
                "name": row.name,
                "target_amount": target,
                "current_balance": current,
                "icon": row.icon or "",
                "color": row.color or "#0d9488",
                "exclude_from_net_worth": row.exclude_from_net_worth,
                "display_order": row.display_order,
                "progress_pct": progress,
            }
        )
    return result


def load_investments_total(user_id: str) -> float:
    """Load total investment portfolio value."""
    # Aggregate: SUM(units * last_unit_price) — F() product computed in-DB
    result = Investment.objects.for_user(user_id).aggregate(
        total=Coalesce(Sum(F("units") * F("last_unit_price")), Decimal(0))
    )
    return float(result["total"])


def load_excluded_va_total(user_id: str) -> float:
    """Load total balance of virtual accounts excluded from net worth."""
    result = (
        VirtualAccount.objects.for_user(user_id)
        .filter(exclude_from_net_worth=True, is_archived=False)
        .aggregate(total=Coalesce(Sum("current_balance"), Decimal(0)))
    )
    return float(result["total"])
