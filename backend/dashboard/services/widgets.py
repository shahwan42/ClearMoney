"""Dashboard widgets — health warnings, budgets, virtual accounts, investments."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from django.db import connection

from .helpers import _parse_jsonb


@dataclass
class HealthWarning:
    """Violated health constraint on an account.
    Go equivalent: service.AccountHealthWarning"""

    account_name: str
    account_id: str
    rule: str  # "min_balance" or "min_monthly_deposit"
    message: str


def load_health_warnings(
    user_id: str, all_accounts: list[dict[str, Any]], tz: ZoneInfo
) -> list[HealthWarning]:
    """Check account health constraints.

    Port of Go's AccountHealthService.CheckAll().
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
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT EXISTS(
                        SELECT 1 FROM transactions
                        WHERE account_id = %s AND user_id = %s AND type = 'income'
                        AND amount >= %s AND date >= %s AND date < %s
                    )
                    """,
                    [
                        acc["id"],
                        user_id,
                        float(min_deposit),
                        month_start,
                        month_end,
                    ],
                )
                row = cursor.fetchone()
                has_deposit = row[0] if row else False

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

    Port of Go's BudgetRepo.GetAllWithSpending().
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
                AND t.currency = b.currency::currency_type
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
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, name, target_amount, current_balance, icon, color,
                   exclude_from_net_worth, display_order
            FROM virtual_accounts
            WHERE user_id = %s AND is_archived = false
            ORDER BY display_order, name
            """,
            [user_id],
        )
        rows = cursor.fetchall()

    result: list[dict[str, Any]] = []
    for row in rows:
        target = float(row[2]) if row[2] else 0.0
        current = float(row[3])
        progress = (current / target * 100) if target > 0 else 0.0
        result.append(
            {
                "id": str(row[0]),
                "name": row[1],
                "target_amount": target,
                "current_balance": current,
                "icon": row[4] or "",
                "color": row[5] or "#0d9488",
                "exclude_from_net_worth": row[6],
                "display_order": row[7],
                "progress_pct": progress,
            }
        )
    return result


def load_investments_total(user_id: str) -> float:
    """Load total investment portfolio value."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COALESCE(SUM(units * last_unit_price), 0) FROM investments WHERE user_id = %s",
            [user_id],
        )
        row = cursor.fetchone()
        return float(row[0]) if row else 0.0


def load_excluded_va_total(user_id: str) -> float:
    """Load total balance of virtual accounts excluded from net worth."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COALESCE(SUM(current_balance), 0)
            FROM virtual_accounts
            WHERE user_id = %s AND exclude_from_net_worth = true AND is_archived = false
            """,
            [user_id],
        )
        row = cursor.fetchone()
        return float(row[0]) if row else 0.0
