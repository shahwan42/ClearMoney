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

from dateutil.relativedelta import relativedelta
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import DecimalField, OuterRef, Subquery, Sum
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Coalesce

from budgets.models import Budget, TotalBudget
from budgets.types import BudgetWithSpending
from core.dates import month_range
from core.status import compute_threshold_status
from transactions.models import Transaction

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

    def _month_range(self) -> tuple[date, date]:
        """Current month range."""
        return month_range(datetime.now(self.tz).date())

    def get_all_with_spending(
        self, target_date: date | None = None
    ) -> list[BudgetWithSpending]:
        """Return active budgets with current month's actual spending.

        Annotates budgets with a Subquery against transactions to compute spent
        amount, percentage, and traffic-light status (green/amber/red).
        Includes rollover logic if enabled.
        """
        if not target_date:
            target_date = datetime.now(self.tz).date()
        month_start, month_end = month_range(target_date)

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
            .annotate(
                spent_amount=Coalesce(spending_subquery, Decimal(0)),
                category_name_en=KeyTextTransform("en", "category__name"),
            )
            .order_by("category_name_en")
        )

        # Pre-calculate previous month's remaining for rollover
        prev_month_start, prev_month_end = month_range(
            target_date - relativedelta(months=1)
        )

        budgets: list[BudgetWithSpending] = []
        for b in rows:
            limit_amt = float(b.monthly_limit)

            effective_limit = limit_amt
            rollover_amt = 0.0

            if b.rollover_enabled:
                # Get last month's spending
                prev_spent_agg = (
                    Transaction.objects.filter(
                        category_id=b.category_id,
                        user_id=self.user_id,
                        type="expense",
                        currency=b.currency,
                        date__gte=prev_month_start,
                        date__lt=prev_month_end,
                    )
                    .aggregate(total=Coalesce(Sum("amount"), Decimal(0)))
                )

                prev_spent = float(prev_spent_agg["total"])
                carryover = max(0.0, limit_amt - prev_spent)

                if b.max_rollover is not None:
                    carryover = min(carryover, float(b.max_rollover))

                rollover_amt = carryover
                effective_limit += rollover_amt

            spent = float(b.spent_amount)
            pct = (spent / effective_limit * 100) if effective_limit > 0 else 0.0
            remaining = effective_limit - spent

            status = compute_threshold_status(pct, (80.0, 100.0))

            budgets.append(
                BudgetWithSpending(
                    id=str(b.id),
                    category_id=str(b.category_id),
                    monthly_limit=limit_amt,
                    currency=b.currency,
                    category_name=b.category.get_display_name(),
                    category_icon=b.category.icon or "",
                    spent=spent,
                    remaining=remaining,
                    percentage=pct,
                    status=status,
                    rollover_amount=rollover_amt,
                    effective_limit=effective_limit,
                )
            )
        return budgets

    def copy_last_month_budgets(self) -> int:
        """Create budgets for categories that had spending last month but no budget yet.

        Uses last month's actual spending as the new monthly limit.
        Returns the number of budgets created.
        """
        today = datetime.now(self.tz).date()
        prev_month_start, prev_month_end = month_range(today - relativedelta(months=1))

        # 1. Find all categories with spending last month
        last_month_spending = (
            Transaction.objects.filter(
                user_id=self.user_id,
                type="expense",
                date__gte=prev_month_start,
                date__lt=prev_month_end,
            )
            .values("category_id", "currency")
            .annotate(total=Sum("amount"))
        )

        created_count = 0
        for item in last_month_spending:
            cat_id = item["category_id"]
            if not cat_id:
                continue

            currency = item["currency"]
            limit = float(item["total"])

            # Skip if budget already exists for this category/currency
            if Budget.objects.filter(
                user_id=self.user_id, category_id=cat_id, currency=currency
            ).exists():
                continue

            try:
                self.create(
                    category_id=str(cat_id), monthly_limit=limit, currency=currency
                )
                created_count += 1
            except Exception as e:
                logger.warning("failed to copy budget for cat=%s: %s", cat_id, e)

        return created_count

    def get_budget_with_transactions(self, budget_id: str) -> dict[str, Any]:
        """Return a budget with its contributing transactions for the current month."""
        budget = self._qs().select_related("category").get(id=budget_id)

        month_start, month_end = self._month_range()

        transactions = (
            Transaction.objects.filter(
                category_id=budget.category_id,
                user_id=self.user_id,
                type="expense",
                currency=budget.currency,
                date__gte=month_start,
                date__lt=month_end,
            )
            .select_related("account")
            .order_by("-date", "-created_at")
        )

        limit_amt = float(budget.monthly_limit)
        # TODO: Apply rollover logic here too if needed for detail view
        spent = sum(float(tx.amount) for tx in transactions)
        pct = (spent / limit_amt * 100) if limit_amt > 0 else 0.0
        remaining = limit_amt - spent

        status = compute_threshold_status(pct, (80.0, 100.0))

        return {
            "id": str(budget.id),
            "category_id": str(budget.category_id),
            "category_name": budget.category.get_display_name(),
            "category_icon": budget.category.icon or "",
            "monthly_limit": limit_amt,
            "currency": budget.currency,
            "spent": spent,
            "remaining": remaining,
            "percentage": pct,
            "status": status,
            "transactions": [
                {
                    "id": str(tx.id),
                    "date": tx.date,
                    "note": tx.note or "",
                    "amount": float(tx.amount),
                    "account_name": tx.account.name if tx.account else "",
                }
                for tx in transactions
            ],
        }

    def create(
        self,
        category_id: str,
        monthly_limit: float,
        currency: str = "EGP",
        rollover_enabled: bool = False,
        max_rollover: float | None = None,
    ) -> dict[str, Any]:
        """Create a new budget with validation."""
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
            rollover_enabled=rollover_enabled,
            max_rollover=max_rollover,
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
            "rollover_enabled": budget.rollover_enabled,
            "max_rollover": float(budget.max_rollover) if budget.max_rollover else None,
            "created_at": budget.created_at,
            "updated_at": budget.updated_at,
        }

    def update(
        self,
        budget_id: str,
        monthly_limit: float | None = None,
        rollover_enabled: bool | None = None,
        max_rollover: float | None = None,
    ) -> dict[str, Any]:
        """Update a budget's fields."""
        update_data = {}
        if monthly_limit is not None:
            if monthly_limit <= 0:
                raise ValueError("Monthly limit must be positive")
            update_data["monthly_limit"] = monthly_limit

        if rollover_enabled is not None:
            update_data["rollover_enabled"] = rollover_enabled

        if max_rollover is not None:
            update_data["max_rollover"] = max_rollover

        if not update_data:
            budget = self._qs().get(id=budget_id)
            return {
                "id": str(budget.id),
                "category_id": str(budget.category_id),
                "monthly_limit": float(budget.monthly_limit),
                "currency": budget.currency,
                "is_active": budget.is_active,
                "created_at": budget.created_at,
                "updated_at": budget.updated_at,
            }

        count = (
            self._qs()
            .filter(id=budget_id)
            .update(**update_data, updated_at=datetime.now())
        )
        if count == 0:
            raise ObjectDoesNotExist(f"Budget not found: {budget_id}")

        budget = self._qs().get(id=budget_id)
        logger.info(
            "budget.updated id=%s user=%s",
            budget_id,
            self.user_id,
        )
        return {
            "id": str(budget.id),
            "category_id": str(budget.category_id),
            "monthly_limit": float(budget.monthly_limit),
            "currency": budget.currency,
            "is_active": budget.is_active,
            "rollover_enabled": budget.rollover_enabled,
            "max_rollover": float(budget.max_rollover) if budget.max_rollover else None,
            "created_at": budget.created_at,
            "updated_at": budget.updated_at,
        }

    def delete(self, budget_id: str) -> bool:
        """Delete budget record."""
        count, _ = self._qs().filter(id=budget_id).delete()
        return bool(count > 0)

    def get_total_budget(self, currency: str = "EGP") -> float:
        """Get the total monthly budget limit for a currency."""
        row = (
            TotalBudget.objects.for_user(self.user_id)
            .filter(currency=currency)
            .values_list("monthly_limit", flat=True)
            .first()
        )
        return float(row) if row else 0.0

    def set_total_budget(self, limit: Decimal, currency: str = "EGP") -> None:
        """Create or update the total monthly budget limit."""
        if limit < 0:
            raise ValueError("Total budget limit cannot be negative")

        TotalBudget.objects.update_or_create(
            user_id=self.user_id,
            currency=currency,
            defaults={"monthly_limit": limit, "updated_at": datetime.now()},
        )
        logger.info(
            "total_budget.set limit=%s currency=%s user=%s",
            limit,
            currency,
            self.user_id,
        )

    def delete_total_budget(self, currency: str = "EGP") -> bool:
        """Remove the total monthly budget limit for a currency."""
        count, _ = (
            TotalBudget.objects.for_user(self.user_id).filter(currency=currency).delete()
        )
        deleted = bool(count > 0)
        if deleted:
            logger.info(
                "total_budget.deleted currency=%s user=%s", currency, self.user_id
            )
        return deleted
