"""
Budget service tests — CRUD and spending progress computation.

Tests run against the real database with --reuse-db.
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from auth_app.currency import (
    set_user_active_currencies,
    set_user_selected_display_currency,
)
from budgets.services import BudgetService
from conftest import SessionFactory, UserFactory
from tests.factories import (
    AccountFactory,
    BudgetFactory,
    CategoryFactory,
    CurrencyFactory,
    InstitutionFactory,
    TransactionFactory,
)

TZ = ZoneInfo("Africa/Cairo")


@pytest.fixture
def budget_data(db):
    """User + two expense categories for budget tests."""
    user = UserFactory()
    SessionFactory(user=user)
    user_id = str(user.id)
    cat1 = CategoryFactory(user_id=user.id, name={"en": "Groceries"}, type="expense")
    cat2 = CategoryFactory(user_id=user.id, name={"en": "Transport"}, type="expense")

    yield {
        "user_id": user_id,
        "cat1_id": str(cat1.id),
        "cat2_id": str(cat2.id),
    }


def _svc(user_id: str) -> BudgetService:
    return BudgetService(user_id, TZ)


def _enable_currencies(user_id: str, *codes: str) -> None:
    for index, code in enumerate(codes):
        CurrencyFactory(code=code, name=code, display_order=index)
    set_user_active_currencies(user_id, list(codes))


# ---------------------------------------------------------------------------
# get_all_with_spending
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGetAllWithSpending:
    def test_empty(self, budget_data):
        svc = _svc(budget_data["user_id"])
        result = svc.get_all_with_spending()
        assert result == []

    def test_with_budget_no_spending(self, budget_data):
        svc = _svc(budget_data["user_id"])
        svc.create(budget_data["cat1_id"], 5000.0, "EGP")
        result = svc.get_all_with_spending()

        assert len(result) == 1
        b = result[0]
        assert b.category_name == "Groceries"
        assert b.monthly_limit == 5000.0
        assert b.spent == 0.0
        assert b.remaining == 5000.0
        assert b.percentage == 0.0
        assert b.status == "green"

    def test_with_spending_green(self, budget_data):
        """Under 80% — green status."""
        svc = _svc(budget_data["user_id"])
        svc.create(budget_data["cat1_id"], 1000.0, "EGP")

        # Create an account + expense transaction for 500 (50%)
        _create_expense(budget_data["user_id"], budget_data["cat1_id"], 500.0)

        result = svc.get_all_with_spending()
        assert len(result) == 1
        b = result[0]
        assert b.spent == 500.0
        assert b.remaining == 500.0
        assert b.percentage == 50.0
        assert b.status == "green"

    def test_with_spending_amber(self, budget_data):
        """Between 80% and 100% — amber status."""
        svc = _svc(budget_data["user_id"])
        svc.create(budget_data["cat1_id"], 1000.0, "EGP")

        _create_expense(budget_data["user_id"], budget_data["cat1_id"], 850.0)

        result = svc.get_all_with_spending()
        b = result[0]
        assert b.spent == 850.0
        assert b.percentage == 85.0
        assert b.status == "amber"

    def test_with_spending_red(self, budget_data):
        """100% or more — red status."""
        svc = _svc(budget_data["user_id"])
        svc.create(budget_data["cat1_id"], 1000.0, "EGP")

        _create_expense(budget_data["user_id"], budget_data["cat1_id"], 1200.0)

        result = svc.get_all_with_spending()
        b = result[0]
        assert b.spent == 1200.0
        assert b.remaining == -200.0
        assert b.percentage == 120.0
        assert b.status == "red"

    def test_only_counts_current_month(self, budget_data):
        """Transactions from last month should not count."""
        svc = _svc(budget_data["user_id"])
        svc.create(budget_data["cat1_id"], 1000.0, "EGP")

        # Last month's transaction — should NOT count
        last_month = date.today().replace(day=1) - timedelta(days=1)
        _create_expense(
            budget_data["user_id"], budget_data["cat1_id"], 999.0, tx_date=last_month
        )

        result = svc.get_all_with_spending()
        assert result[0].spent == 0.0


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestBudgetCreate:
    def test_creates_budget(self, budget_data):
        svc = _svc(budget_data["user_id"])
        result = svc.create(budget_data["cat1_id"], 5000.0, "EGP")

        assert result["id"] is not None
        assert result["monthly_limit"] == 5000.0
        assert result["currency"] == "EGP"
        assert result["is_active"] is True

    def test_defaults_currency_to_egp(self, budget_data):
        _enable_currencies(budget_data["user_id"], "EGP", "EUR")
        set_user_selected_display_currency(budget_data["user_id"], "EUR")

        svc = _svc(budget_data["user_id"])
        result = svc.create(budget_data["cat1_id"], 1000.0, "")

        assert result["currency"] == "EUR"

    def test_missing_category_raises(self, budget_data):
        svc = _svc(budget_data["user_id"])
        with pytest.raises(ValueError, match="Category is required"):
            svc.create("", 1000.0, "EGP")

    def test_zero_limit_raises(self, budget_data):
        svc = _svc(budget_data["user_id"])
        with pytest.raises(ValueError, match="Monthly limit must be positive"):
            svc.create(budget_data["cat1_id"], 0.0, "EGP")

    def test_negative_limit_raises(self, budget_data):
        svc = _svc(budget_data["user_id"])
        with pytest.raises(ValueError, match="Monthly limit must be positive"):
            svc.create(budget_data["cat1_id"], -100.0, "EGP")

    def test_duplicate_rejected(self, budget_data):
        from django.db import IntegrityError, transaction

        svc = _svc(budget_data["user_id"])
        svc.create(budget_data["cat1_id"], 1000.0, "EGP")
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                svc.create(budget_data["cat1_id"], 2000.0, "EGP")

    def test_same_category_different_currency_ok(self, budget_data):
        _enable_currencies(budget_data["user_id"], "EGP", "USD")

        svc = _svc(budget_data["user_id"])
        svc.create(budget_data["cat1_id"], 1000.0, "EGP")
        result = svc.create(budget_data["cat1_id"], 500.0, "USD")
        assert result["currency"] == "USD"


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestBudgetDelete:
    def test_deletes_budget(self, budget_data):
        svc = _svc(budget_data["user_id"])
        budget = svc.create(budget_data["cat1_id"], 1000.0, "EGP")
        assert svc.delete(budget["id"]) is True

        # Verify it's gone
        result = svc.get_all_with_spending()
        assert len(result) == 0

    def test_delete_nonexistent_returns_false(self, budget_data):
        svc = _svc(budget_data["user_id"])
        assert svc.delete(str(uuid.uuid4())) is False

    def test_cannot_delete_other_users_budget(self, budget_data):
        svc = _svc(budget_data["user_id"])
        budget = svc.create(budget_data["cat1_id"], 1000.0, "EGP")

        # Try deleting with a different user
        other_svc = _svc(str(uuid.uuid4()))
        assert other_svc.delete(budget["id"]) is False


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestBudgetUpdate:
    def test_updates_monthly_limit(self, budget_data):
        svc = _svc(budget_data["user_id"])
        budget = svc.create(budget_data["cat1_id"], 1000.0, "EGP")
        result = svc.update(budget["id"], 2000.0)

        assert result["monthly_limit"] == 2000.0
        assert result["id"] == budget["id"]

        # Verify persisted
        budgets = svc.get_all_with_spending()
        assert len(budgets) == 1
        assert budgets[0].monthly_limit == 2000.0

    def test_zero_limit_raises(self, budget_data):
        svc = _svc(budget_data["user_id"])
        budget = svc.create(budget_data["cat1_id"], 1000.0, "EGP")
        with pytest.raises(ValueError, match="Monthly limit must be positive"):
            svc.update(budget["id"], 0.0)

    def test_negative_limit_raises(self, budget_data):
        svc = _svc(budget_data["user_id"])
        budget = svc.create(budget_data["cat1_id"], 1000.0, "EGP")
        with pytest.raises(ValueError, match="Monthly limit must be positive"):
            svc.update(budget["id"], -500.0)

    def test_nonexistent_budget_raises(self, budget_data):
        svc = _svc(budget_data["user_id"])
        from django.core.exceptions import ObjectDoesNotExist

        with pytest.raises(ObjectDoesNotExist, match="Budget not found"):
            svc.update(str(uuid.uuid4()), 1000.0)

    def test_cannot_update_other_users_budget(self, budget_data):
        svc = _svc(budget_data["user_id"])
        budget = svc.create(budget_data["cat1_id"], 1000.0, "EGP")

        other_svc = _svc(str(uuid.uuid4()))
        from django.core.exceptions import ObjectDoesNotExist

        with pytest.raises(ObjectDoesNotExist, match="Budget not found"):
            other_svc.update(budget["id"], 999.0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestBudgetEdgeCases:
    """Monetary edge cases: refunds (negative spending) and zero-limit budgets."""

    def test_negative_spending_refund(self, budget_data: dict) -> None:
        """Budget with a refund (income for the same category) — pct stays at 0."""
        svc = _svc(budget_data["user_id"])
        svc.create(budget_data["cat1_id"], 1000.0, "EGP")

        # Only income transactions for this category — spending subquery only counts
        # type='expense', so income (refunds) are excluded and spent stays at 0.
        inst = InstitutionFactory(
            user_id=budget_data["user_id"], name="TestInst", type="bank"
        )
        acct = AccountFactory(
            user_id=budget_data["user_id"],
            institution_id=inst.id,
            name="Test",
            type="savings",
            currency="EGP",
            current_balance=0,
            initial_balance=0,
        )
        TransactionFactory(
            user_id=budget_data["user_id"],
            account_id=acct.id,
            category_id=budget_data["cat1_id"],
            type="income",
            amount=500.0,
            currency="EGP",
            date=date.today(),
            balance_delta=500.0,
        )

        result = svc.get_all_with_spending()
        assert len(result) == 1
        b = result[0]
        # Income transactions don't count as spending — spent is 0
        assert b.spent == 0.0
        assert b.percentage == 0.0
        assert b.status == "green"

    def test_zero_limit_budget_percentage(self, budget_data: dict) -> None:
        """Budget with monthly_limit=0 is rejected by create validation."""
        svc = _svc(budget_data["user_id"])
        # The service rejects monthly_limit <= 0, so zero-limit cannot be created
        with pytest.raises(ValueError, match="Monthly limit must be positive"):
            svc.create(budget_data["cat1_id"], 0.0, "EGP")


# ---------------------------------------------------------------------------
# get_budget_with_transactions
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGetBudgetWithTransactions:
    """Budget detail: returns budget info + contributing transactions."""

    def test_returns_budget_and_transactions(self, budget_data: dict) -> None:
        """Happy path: budget with 2 expense transactions returns both."""
        svc = _svc(budget_data["user_id"])
        budget = svc.create(budget_data["cat1_id"], 5000.0, "EGP")
        _create_expense(budget_data["user_id"], budget_data["cat1_id"], 300.0)
        _create_expense(budget_data["user_id"], budget_data["cat1_id"], 700.0)

        result = svc.get_budget_with_transactions(budget["id"])
        assert result["category_name"] == "Groceries"
        assert result["monthly_limit"] == 5000.0
        assert result["spent"] == 1000.0
        assert len(result["transactions"]) == 2

    def test_empty_transactions(self, budget_data: dict) -> None:
        """Budget with no transactions returns empty list."""
        svc = _svc(budget_data["user_id"])
        budget = svc.create(budget_data["cat1_id"], 5000.0, "EGP")

        result = svc.get_budget_with_transactions(budget["id"])
        assert result["transactions"] == []
        assert result["spent"] == 0.0

    def test_excludes_previous_month(self, budget_data: dict) -> None:
        """Transactions from last month are excluded."""
        svc = _svc(budget_data["user_id"])
        budget = svc.create(budget_data["cat1_id"], 5000.0, "EGP")
        last_month = date.today().replace(day=1) - timedelta(days=1)
        _create_expense(
            budget_data["user_id"], budget_data["cat1_id"], 999.0, tx_date=last_month
        )
        _create_expense(budget_data["user_id"], budget_data["cat1_id"], 200.0)

        result = svc.get_budget_with_transactions(budget["id"])
        assert len(result["transactions"]) == 1
        assert result["spent"] == 200.0

    def test_excludes_income_transactions(self, budget_data: dict) -> None:
        """Income transactions in the same category are excluded."""
        svc = _svc(budget_data["user_id"])
        budget = svc.create(budget_data["cat1_id"], 5000.0, "EGP")
        _create_expense(budget_data["user_id"], budget_data["cat1_id"], 500.0)
        # Create an income transaction in the same category
        inst = InstitutionFactory(
            user_id=budget_data["user_id"], name="TestInst", type="bank"
        )
        acct = AccountFactory(
            user_id=budget_data["user_id"],
            institution_id=inst.id,
            name="Test",
            type="savings",
            currency="EGP",
            current_balance=0,
            initial_balance=0,
        )
        TransactionFactory(
            user_id=budget_data["user_id"],
            account_id=acct.id,
            category_id=budget_data["cat1_id"],
            type="income",
            amount=1000.0,
            currency="EGP",
            date=date.today(),
            balance_delta=1000.0,
        )

        result = svc.get_budget_with_transactions(budget["id"])
        assert len(result["transactions"]) == 1
        assert result["spent"] == 500.0

    def test_other_users_budget_raises(self, budget_data: dict) -> None:
        """Accessing another user's budget raises DoesNotExist."""
        from budgets.models import Budget

        svc = _svc(budget_data["user_id"])
        budget = svc.create(budget_data["cat1_id"], 5000.0, "EGP")

        other_svc = _svc(str(uuid.uuid4()))
        with pytest.raises(Budget.DoesNotExist):
            other_svc.get_budget_with_transactions(budget["id"])

    def test_transactions_sorted_newest_first(self, budget_data: dict) -> None:
        """Transactions are returned sorted by date descending."""
        svc = _svc(budget_data["user_id"])
        budget = svc.create(budget_data["cat1_id"], 5000.0, "EGP")
        today = date.today()
        earlier = today.replace(day=1)
        _create_expense(
            budget_data["user_id"], budget_data["cat1_id"], 100.0, tx_date=earlier
        )
        _create_expense(
            budget_data["user_id"], budget_data["cat1_id"], 200.0, tx_date=today
        )

        result = svc.get_budget_with_transactions(budget["id"])
        dates = [tx["date"] for tx in result["transactions"]]
        assert dates == sorted(dates, reverse=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_expense(
    user_id: str,
    category_id: str,
    amount: float,
    tx_date: date | None = None,
) -> None:
    """Insert a test expense transaction with an account.

    Creates a temporary institution + account via factories, then inserts a transaction.
    """
    if tx_date is None:
        tx_date = date.today()

    inst = InstitutionFactory(user_id=user_id, name="TestInst", type="bank")
    acct = AccountFactory(
        user_id=user_id,
        institution_id=inst.id,
        name="Test",
        type="savings",
        currency="EGP",
        current_balance=0,
        initial_balance=0,
    )
    TransactionFactory(
        user_id=user_id,
        account_id=acct.id,
        category_id=category_id,
        type="expense",
        amount=amount,
        currency="EGP",
        date=tx_date,
        balance_delta=-amount,
    )


# ---------------------------------------------------------------------------
# TotalBudget service
# ---------------------------------------------------------------------------


@pytest.fixture
def user_with_expenses(db):
    """User + EGP account + 8,000 in expenses this month."""
    user = UserFactory()
    SessionFactory(user=user)
    inst = InstitutionFactory(user_id=str(user.id), name="Bank", type="bank")
    account = AccountFactory(
        user_id=str(user.id),
        institution_id=inst.id,
        name="EGP",
        type="savings",
        currency="EGP",
        current_balance=0,
        initial_balance=0,
    )
    cat = CategoryFactory(user_id=user.id, name={"en": "General"}, type="expense")
    today = date.today().replace(day=1)
    for amount in [3000, 2500, 1500, 1000]:
        TransactionFactory(
            user_id=str(user.id),
            account_id=account.id,
            category_id=str(cat.id),
            type="expense",
            amount=Decimal(str(amount)),
            currency="EGP",
            date=today,
            balance_delta=-amount,
        )
    return {
        "user_id": str(user.id),
        "account": account,
        "category": cat,
    }


@pytest.mark.django_db
class TestTotalBudgetService:
    """TotalBudget CRUD and spending calculation."""

    def test_set_total_budget(self, user_with_expenses: dict) -> None:
        svc = _svc(user_with_expenses["user_id"])
        result = svc.set_total_budget(Decimal("15000"), "EGP")
        assert result["monthly_limit"] == Decimal("15000")
        assert result["currency"] == "EGP"

    def test_get_total_budget_with_spending(self, user_with_expenses: dict) -> None:
        svc = _svc(user_with_expenses["user_id"])
        svc.set_total_budget(Decimal("15000"), "EGP")
        result = svc.get_total_budget("EGP")
        assert result is not None
        assert result["monthly_limit"] == Decimal("15000")
        assert result["spent"] == Decimal("8000")
        assert result["remaining"] == Decimal("7000")
        assert result["percentage"] == pytest.approx(53.3, abs=0.1)
        assert result["status"] == "green"

    def test_total_budget_amber_status(self, user_with_expenses: dict) -> None:
        svc = _svc(user_with_expenses["user_id"])
        svc.set_total_budget(Decimal("9000"), "EGP")
        result = svc.get_total_budget("EGP")
        assert result is not None
        assert result["status"] == "amber"

    def test_total_budget_red_status(self, user_with_expenses: dict) -> None:
        svc = _svc(user_with_expenses["user_id"])
        svc.set_total_budget(Decimal("7000"), "EGP")
        result = svc.get_total_budget("EGP")
        assert result is not None
        assert result["status"] == "red"

    def test_category_sum_warning(self, user_with_expenses: dict) -> None:
        uid = user_with_expenses["user_id"]
        svc = _svc(uid)
        svc.set_total_budget(Decimal("10000"), "EGP")
        cat1 = CategoryFactory(user_id=uid, name={"en": "Cat1"}, type="expense")
        cat2 = CategoryFactory(user_id=uid, name={"en": "Cat2"}, type="expense")
        BudgetFactory(user_id=uid, category_id=cat1.id, monthly_limit=Decimal("7000"))
        BudgetFactory(user_id=uid, category_id=cat2.id, monthly_limit=Decimal("5000"))
        result = svc.get_total_budget("EGP")
        assert result is not None
        assert result["category_sum_exceeds"] is True
        assert result["category_sum"] == Decimal("12000")

    def test_upsert_total_budget(self, db: None) -> None:
        user = UserFactory()
        svc = _svc(str(user.id))
        svc.set_total_budget(Decimal("10000"), "EGP")
        svc.set_total_budget(Decimal("15000"), "EGP")
        result = svc.get_total_budget("EGP")
        assert result is not None
        assert result["monthly_limit"] == Decimal("15000")

    def test_delete_total_budget(self, db: None) -> None:
        user = UserFactory()
        svc = _svc(str(user.id))
        svc.set_total_budget(Decimal("10000"), "EGP")
        svc.delete_total_budget("EGP")
        result = svc.get_total_budget("EGP")
        assert result is None

    def test_income_not_counted(self, user_with_expenses: dict) -> None:
        account = user_with_expenses["account"]
        TransactionFactory(
            user_id=user_with_expenses["user_id"],
            account_id=account.id,
            category_id=str(user_with_expenses["category"].id),
            type="income",
            amount=Decimal("5000"),
            currency="EGP",
            date=date.today().replace(day=1),
            balance_delta=5000,
        )
        svc = _svc(user_with_expenses["user_id"])
        svc.set_total_budget(Decimal("15000"), "EGP")
        result = svc.get_total_budget("EGP")
        assert result is not None
        assert result["spent"] == Decimal("8000")

    def test_uncategorized_expenses_counted(self, user_with_expenses: dict) -> None:
        """Expenses with no category still count toward total budget."""
        account = user_with_expenses["account"]
        TransactionFactory(
            user_id=user_with_expenses["user_id"],
            account_id=account.id,
            category_id=None,
            type="expense",
            amount=Decimal("1000"),
            currency="EGP",
            date=date.today().replace(day=1),
            balance_delta=-1000,
        )
        svc = _svc(user_with_expenses["user_id"])
        svc.set_total_budget(Decimal("15000"), "EGP")
        result = svc.get_total_budget("EGP")
        assert result is not None
        assert result["spent"] == Decimal("9000")

    def test_get_nonexistent_total_budget(self, db: None) -> None:
        user = UserFactory()
        svc = _svc(str(user.id))
        result = svc.get_total_budget("EGP")
        assert result is None

    def test_different_currencies_independent(self, db: None) -> None:
        user = UserFactory()
        _enable_currencies(str(user.id), "EGP", "USD")
        svc = _svc(str(user.id))
        svc.set_total_budget(Decimal("15000"), "EGP")
        svc.set_total_budget(Decimal("500"), "USD")
        egp = svc.get_total_budget("EGP")
        usd = svc.get_total_budget("USD")
        assert egp is not None
        assert usd is not None
        assert egp["monthly_limit"] == Decimal("15000")
        assert usd["monthly_limit"] == Decimal("500")

    def test_negative_limit_raises(self, db: None) -> None:
        user = UserFactory()
        svc = _svc(str(user.id))
        with pytest.raises(ValueError, match="Monthly limit must be positive"):
            svc.set_total_budget(Decimal("-1000"), "EGP")

    def test_zero_limit_raises(self, db: None) -> None:
        user = UserFactory()
        svc = _svc(str(user.id))
        with pytest.raises(ValueError, match="Monthly limit must be positive"):
            svc.set_total_budget(Decimal("0"), "EGP")
