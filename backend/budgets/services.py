"""
Budget service — business logic for monthly spending limits per category.

Combines service and repository layers into a single class. Validates input,
queries via Django ORM, computes spending progress (green/amber/red), and logs mutations.

The spending query is the same one used by DashboardService._load_budgets_with_spending().
Both compute current-month spending by annotating budgets with a Subquery against
transactions filtered by type='expense' and matching currency.
"""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from django.db.models import DecimalField, OuterRef, Subquery, Sum
from django.db.models.functions import Coalesce

from core.models import Budget, Transaction

logger = logging.getLogger(__name__)


class BudgetService:
    """Handles budget CRUD and spending progress computation.

    All queries are scoped to the authenticated user via user_id.
    """

    def __init__(self, user_id: str, tz: ZoneInfo) -> None:
        self.user_id = user_id
        self.tz = tz

    def _qs(self) -> Any:
        """Base queryset scoped to the current user."""
        return Budget.objects.for_user(self.user_id)

    def get_all_with_spending(self) -> list[dict[str, Any]]:
        """Return active budgets with current month's actual spending.

        Annotates budgets with a Subquery against transactions to compute spent
        amount, percentage, and traffic-light status (green/amber/red).

        Uses Subquery because Transaction.category has related_name="+"
        which disables reverse FK access from Category/Budget.
        """
        today = datetime.now(self.tz).date()
        month_start = today.replace(day=1)
        if today.month == 12:
            month_end = date(today.year + 1, 1, 1)
        else:
            month_end = date(today.year, today.month + 1, 1)

        # Subquery: sum of expense transactions for the same category, user, currency
        # in the current month. Uses OuterRef to correlate with the outer Budget queryset.
        spending_subquery = Subquery(
            Transaction.objects.filter(
                category_id=OuterRef("category_id"),
                user_id=OuterRef("user_id"),
                type="expense",
                date__gte=month_start,
                date__lt=month_end,
                currency=OuterRef("currency"),
            )
            .values("category_id")
            .annotate(total=Sum("amount"))
            .values("total")[:1],
            output_field=DecimalField(),
        )

        rows = (
            self._qs()
            .filter(is_active=True)
            .select_related("category")
            .annotate(spent_amount=Coalesce(spending_subquery, Decimal(0)))
            .order_by("category__name")
        )

        budgets: list[dict[str, Any]] = []
        for b in rows:
            limit_amt = float(b.monthly_limit)
            spent = float(b.spent_amount)
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
                    "id": str(b.id),
                    "category_id": str(b.category_id),
                    "monthly_limit": limit_amt,
                    "currency": b.currency,
                    "category_name": b.category.name,
                    "category_icon": b.category.icon or "",
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

        Validates that category_id is provided and monthly_limit is positive.
        Currency defaults to 'EGP'.

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

        budget = Budget.objects.create(
            user_id=self.user_id,
            category_id=category_id,
            monthly_limit=monthly_limit,
            currency=currency,
        )

        logger.info(
            "budget.created currency=%s category_id=%s user=%s",
            currency,
            category_id,
            self.user_id,
        )
        return {
            "id": str(budget.id),
            "category_id": str(budget.category_id),
            "monthly_limit": float(budget.monthly_limit),
            "currency": budget.currency,
            "is_active": budget.is_active,
            "created_at": budget.created_at,
            "updated_at": budget.updated_at,
        }

    def delete(self, budget_id: str) -> bool:
        """Delete a budget by ID.

        Only deletes budgets belonging to the authenticated user.
        Returns True if a row was deleted, False if not found.
        """
        count, _ = self._qs().filter(id=budget_id).delete()
        deleted = bool(count > 0)

        if deleted:
            logger.info("budget.deleted id=%s user=%s", budget_id, self.user_id)
        return deleted
