"""
Budget service — business logic for monthly spending limits per category.

Port of Go's BudgetService (internal/service/budget.go) and BudgetRepo
(internal/repository/budget.go). Combines both layers into a single service
since Django views call the service directly (no separate repository layer).

Like Laravel's BudgetService — validates input, executes SQL, computes
spending progress (green/amber/red), and logs mutation events.

The spending query is the same one used by DashboardService._load_budgets_with_spending()
(backend/dashboard/services.py:876). Both compute current-month spending by JOINing
budgets with transactions filtered by type='expense' and matching currency.
"""

import logging
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from django.db import connection

logger = logging.getLogger(__name__)


class BudgetService:
    """Handles budget CRUD and spending progress computation.

    Like Go's BudgetService + BudgetRepo combined. All queries are
    scoped to the authenticated user via user_id.
    """

    def __init__(self, user_id: str, tz: ZoneInfo) -> None:
        self.user_id = user_id
        self.tz = tz

    def get_all_with_spending(self) -> list[dict[str, Any]]:
        """Return active budgets with current month's actual spending.

        Port of Go's BudgetRepo.GetAllWithSpending(). JOINs budgets with
        categories and transactions to compute spent amount, percentage,
        and traffic-light status (green/amber/red).
        """
        today = datetime.now(self.tz).date()
        month_start = today.replace(day=1)
        if today.month == 12:
            month_end = date(today.year + 1, 1, 1)
        else:
            month_end = date(today.year, today.month + 1, 1)

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT b.id, b.category_id, b.monthly_limit, b.currency,
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
                [month_start, month_end, self.user_id],
            )
            rows = cursor.fetchall()

        budgets: list[dict[str, Any]] = []
        for row in rows:
            limit_amt = float(row[2])
            spent = float(row[6])
            pct = (spent / limit_amt * 100) if limit_amt > 0 else 0.0
            remaining = limit_amt - spent

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
                    "category_name": row[4],
                    "category_icon": row[5],
                    "spent": spent,
                    "remaining": remaining,
                    "percentage": pct,
                    "status": status,
                }
            )
        return budgets

    def create(
        self,
        category_id: str,
        monthly_limit: float,
        currency: str = "EGP",
    ) -> dict[str, Any]:
        """Create a new budget with validation.

        Port of Go's BudgetService.Create(). Validates that category_id
        is provided and monthly_limit is positive. Currency defaults to 'EGP'.

        Raises:
            ValueError: If category_id is empty or monthly_limit <= 0.
            IntegrityError: If a budget already exists for this user+category+currency.
        """
        if not category_id:
            raise ValueError("Category is required")
        if monthly_limit <= 0:
            raise ValueError("Monthly limit must be positive")
        if not currency:
            currency = "EGP"

        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO budgets (user_id, category_id, monthly_limit, currency)
                VALUES (%s, %s, %s, %s)
                RETURNING id, category_id, monthly_limit, currency, is_active,
                          created_at, updated_at
                """,
                [self.user_id, category_id, monthly_limit, currency],
            )
            row = cursor.fetchone()

        if row is None:
            raise ValueError("Failed to create budget")

        logger.info(
            "budget.created currency=%s category_id=%s user=%s",
            currency,
            category_id,
            self.user_id,
        )
        return {
            "id": str(row[0]),
            "category_id": str(row[1]),
            "monthly_limit": float(row[2]),
            "currency": row[3],
            "is_active": row[4],
            "created_at": row[5],
            "updated_at": row[6],
        }

    def delete(self, budget_id: str) -> bool:
        """Delete a budget by ID.

        Port of Go's BudgetService.Delete(). Only deletes budgets
        belonging to the authenticated user.

        Returns True if a row was deleted, False if not found.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM budgets WHERE id = %s AND user_id = %s",
                [budget_id, self.user_id],
            )
            deleted: bool = cursor.rowcount > 0

        if deleted:
            logger.info("budget.deleted id=%s user=%s", budget_id, self.user_id)
        return deleted
