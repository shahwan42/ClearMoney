"""Dashboard widgets — health warnings, budgets, virtual accounts, investments.

Budget spending logic is owned by BudgetService. Health warnings are owned
by accounts.services. This module re-exports and adapts for dashboard use.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from django.db.models import F, Sum
from django.db.models.functions import Coalesce

from accounts.services import load_health_warnings  # noqa: F401
from accounts.types import HealthWarning  # noqa: F401
from budgets.services import BudgetService
from investments.models import Investment
from virtual_accounts.models import VirtualAccount


def load_budgets_with_spending(user_id: str, tz: ZoneInfo) -> list[dict[str, Any]]:
    """Load budgets with current month's actual spending.

    Delegates to BudgetService.get_all_with_spending() and converts typed
    BudgetWithSpending dataclasses to dicts for template rendering.
    """
    svc = BudgetService(user_id, tz)
    typed_budgets = svc.get_all_with_spending()

    return [
        {
            "id": b.id,
            "category_id": b.category_id,
            "monthly_limit": b.monthly_limit,
            "currency": b.currency,
            "category_name": b.category_name,
            "category_icon": b.category_icon,
            "spent": b.spent,
            "percentage": b.percentage,
            "status": b.status,
        }
        for b in typed_budgets
    ]


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
    
    # Sort to highlight closest-to-goal virtual accounts
    result.sort(key=lambda x: (x["target_amount"] > 0, x["progress_pct"]), reverse=True)
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
