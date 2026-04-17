"""Tests for BudgetService rollover and copy logic."""

import datetime
from zoneinfo import ZoneInfo

import pytest

from budgets.services import BudgetService
from tests.factories import (
    AccountFactory,
    CategoryFactory,
    InstitutionFactory,
    TransactionFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestBudgetRollover:
    def test_rollover_calculation(self):
        user = UserFactory()
        svc = BudgetService(str(user.id), ZoneInfo("UTC"))
        category = CategoryFactory(user_id=user.id, type="expense", name={"en": "Food"})

        # Create budget with rollover
        svc.create(
            category_id=str(category.id), monthly_limit=1000, rollover_enabled=True
        )

        # Last month: spent 600 of 1000 -> 400 rollover
        today = datetime.date(2026, 4, 16)
        last_month_mid = datetime.date(2026, 3, 15)

        inst = InstitutionFactory(user_id=user.id)
        account = AccountFactory(
            user_id=user.id, institution_id=inst.id, currency="EGP"
        )

        TransactionFactory(
            user_id=user.id,
            category_id=category.id,
            account_id=account.id,
            type="expense",
            amount=600,
            date=last_month_mid,
            currency="EGP",
        )

        # This month: spent 200
        TransactionFactory(
            user_id=user.id,
            category_id=category.id,
            account_id=account.id,
            type="expense",
            amount=200,
            date=today,
            currency="EGP",
        )

        budgets = svc.get_all_with_spending(target_date=today)
        b = budgets[0]

        assert b.rollover_amount == 400.0
        assert b.effective_limit == 1400.0
        assert b.spent == 200.0
        assert b.remaining == 1200.0

    def test_max_rollover_respected(self):
        user = UserFactory()
        svc = BudgetService(str(user.id), ZoneInfo("UTC"))
        category = CategoryFactory(user_id=user.id, type="expense")

        # Limit 1000, rollover 400, but max_rollover 200
        svc.create(
            category_id=str(category.id),
            monthly_limit=1000,
            rollover_enabled=True,
            max_rollover=200,
        )

        last_month_mid = datetime.date(2026, 3, 15)
        inst = InstitutionFactory(user_id=user.id)
        account = AccountFactory(
            user_id=user.id, institution_id=inst.id, currency="EGP"
        )

        TransactionFactory(
            user_id=user.id,
            category_id=category.id,
            account_id=account.id,
            type="expense",
            amount=600,
            date=last_month_mid,
            currency="EGP",
        )

        budgets = svc.get_all_with_spending(target_date=datetime.date(2026, 4, 16))
        b = budgets[0]

        assert b.rollover_amount == 200.0
        assert b.effective_limit == 1200.0


@pytest.mark.django_db
class TestBudgetCopy:
    def test_copy_last_month_budgets(self):
        user = UserFactory()
        svc = BudgetService(str(user.id), ZoneInfo("UTC"))
        cat1 = CategoryFactory(user_id=user.id, type="expense", name={"en": "Food"})
        cat2 = CategoryFactory(user_id=user.id, type="expense", name={"en": "Rent"})

        inst = InstitutionFactory(user_id=user.id)
        account = AccountFactory(
            user_id=user.id, institution_id=inst.id, currency="EGP"
        )

        # Spending last month for cat1 and cat2
        last_month_mid = datetime.date(2026, 3, 15)
        TransactionFactory(
            user_id=user.id,
            category_id=cat1.id,
            account_id=account.id,
            type="expense",
            amount=500,
            date=last_month_mid,
        )
        TransactionFactory(
            user_id=user.id,
            category_id=cat2.id,
            account_id=account.id,
            type="expense",
            amount=2000,
            date=last_month_mid,
        )

        # Already have a budget for cat2
        svc.create(category_id=str(cat2.id), monthly_limit=1500)

        # Copy should only create budget for cat1
        created = svc.copy_last_month_budgets()
        assert created == 1

        budgets = svc.get_all_with_spending()
        # Should be 2 budgets: Rent (existing) and Food (copied)
        assert len(budgets) == 2

        b1 = next(b for b in budgets if b.category_id == str(cat1.id))
        assert b1.monthly_limit == 500.0
