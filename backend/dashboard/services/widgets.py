"""Dashboard widgets — health warnings, budgets, virtual accounts, investments."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from django.db import connection
from django.db.models import F, Sum
from django.db.models.functions import Coalesce

from core.models import Investment, Transaction, VirtualAccount

from .helpers import _parse_jsonb


@dataclass
class HealthWarning:
    """Violated health constraint on an account."""

    account_name: str
    account_id: str
    rule: str  # "min_balance" or "min_monthly_deposit"
    message: str


def load_health_warnings(
    user_id: str, all_accounts: list[dict[str, Any]], tz: ZoneInfo
) -> list[HealthWarning]:
    """Check account health constraints.

    Parses health_config JSONB and checks min_balance / min_monthly_deposit.
    """
    warnings: list[HealthWarning] = []
    now = datetime.now(tz)
    today = now.date()
    month_start = today.replace(day=1)
    if today.month == 12:
        month_end = date(today.year + 1, 1, 1)
    else:
        month_end = date(today.year, today.month + 1, 1)

    for acc in all_accounts:
        cfg = _parse_jsonb(acc.get("health_config"))
        if not cfg:
            continue

        # Check minimum balance
        min_balance = cfg.get("min_balance")
        if min_balance is not None and acc["current_balance"] < float(min_balance):
            warnings.append(
                HealthWarning(
                    account_name=acc["name"],
                    account_id=acc["id"],
                    rule="min_balance",
                    message=f"{acc['name']} is below minimum balance",
                )
            )

        # Check minimum monthly deposit
        min_deposit = cfg.get("min_monthly_deposit")
        if min_deposit is not None:
            has_deposit = (
                Transaction.objects.for_user(user_id)
                .filter(
                    account_id=acc["id"],
                    type="income",
                    amount__gte=Decimal(str(min_deposit)),
                    date__gte=month_start,
                    date__lt=month_end,
                )
                .exists()
            )

            if not has_deposit:
                warnings.append(
                    HealthWarning(
                        account_name=acc["name"],
                        account_id=acc["id"],
                        rule="min_monthly_deposit",
                        message=f"{acc['name']} is missing required monthly deposit",
                    )
                )

    return warnings


def load_budgets_with_spending(user_id: str, tz: ZoneInfo) -> list[dict[str, Any]]:
    """Load budgets with current month's actual spending.

    Raw SQL — LEFT JOIN with cross-table aggregation is cleaner than ORM Subquery.
    """
    today = datetime.now(tz).date()
    month_start = today.replace(day=1)
    if today.month == 12:
        month_end = date(today.year + 1, 1, 1)
    else:
        month_end = date(today.year, today.month + 1, 1)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT b.id, b.category_id, b.monthly_limit, b.currency, b.is_active,
                   c.name AS category_name,
                   COALESCE(c.icon, '') AS category_icon,
                   COALESCE(SUM(t.amount), 0) AS spent
            FROM budgets b
            JOIN categories c ON b.category_id = c.id
            LEFT JOIN transactions t ON t.category_id = b.category_id
                AND t.type = 'expense'
                AND t.date >= %s AND t.date < %s
                AND t.currency = b.currency
                AND t.user_id = b.user_id
            WHERE b.is_active = true AND b.user_id = %s
            GROUP BY b.id, c.name, c.icon
            ORDER BY c.name
            """,
            [month_start, month_end, user_id],
        )
        rows = cursor.fetchall()

    budgets: list[dict[str, Any]] = []
    for row in rows:
        limit_amt = float(row[2])
        spent = float(row[7])
        pct = (spent / limit_amt * 100) if limit_amt > 0 else 0.0

        if pct >= 100:
            status = "red"
        elif pct >= 80:
            status = "amber"
        else:
            status = "green"

        budgets.append(
            {
                "id": str(row[0]),
                "category_id": str(row[1]),
                "monthly_limit": limit_amt,
                "currency": row[3],
                "category_name": row[5],
                "category_icon": row[6],
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
