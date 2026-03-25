"""
Budget service tests — CRUD and spending progress computation.

Tests run against the real database with --reuse-db.
"""

import uuid
from datetime import date, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.db import connection

from budgets.services import BudgetService
from conftest import SessionFactory, UserFactory
from core.models import Session, User
from tests.factories import CategoryFactory

TZ = ZoneInfo("Africa/Cairo")


@pytest.fixture
def budget_data(db):
    """User + two expense categories for budget tests."""
    user = UserFactory()
    SessionFactory(user=user)
    user_id = str(user.id)
    cat1 = CategoryFactory(user_id=user.id, name="Groceries", type="expense")
    cat2 = CategoryFactory(user_id=user.id, name="Transport", type="expense")

    yield {
        "user_id": user_id,
        "cat1_id": str(cat1.id),
        "cat2_id": str(cat2.id),
    }

    # Cleanup — order matters for FK constraints
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM transactions WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM budgets WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM categories WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM accounts WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM institutions WHERE user_id = %s", [user_id])
    Session.objects.filter(user=user).delete()
    User.objects.filter(id=user.id).delete()


def _svc(user_id: str) -> BudgetService:
    return BudgetService(user_id, TZ)


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
        assert b["category_name"] == "Groceries"
        assert b["monthly_limit"] == 5000.0
        assert b["spent"] == 0.0
        assert b["remaining"] == 5000.0
        assert b["percentage"] == 0.0
        assert b["status"] == "green"

    def test_with_spending_green(self, budget_data):
        """Under 80% — green status."""
        svc = _svc(budget_data["user_id"])
        svc.create(budget_data["cat1_id"], 1000.0, "EGP")

        # Create an account + expense transaction for 500 (50%)
        _create_expense(budget_data["user_id"], budget_data["cat1_id"], 500.0)

        result = svc.get_all_with_spending()
        assert len(result) == 1
        b = result[0]
        assert b["spent"] == 500.0
        assert b["remaining"] == 500.0
        assert b["percentage"] == 50.0
        assert b["status"] == "green"

    def test_with_spending_amber(self, budget_data):
        """Between 80% and 100% — amber status."""
        svc = _svc(budget_data["user_id"])
        svc.create(budget_data["cat1_id"], 1000.0, "EGP")

        _create_expense(budget_data["user_id"], budget_data["cat1_id"], 850.0)

        result = svc.get_all_with_spending()
        b = result[0]
        assert b["spent"] == 850.0
        assert b["percentage"] == 85.0
        assert b["status"] == "amber"

    def test_with_spending_red(self, budget_data):
        """100% or more — red status."""
        svc = _svc(budget_data["user_id"])
        svc.create(budget_data["cat1_id"], 1000.0, "EGP")

        _create_expense(budget_data["user_id"], budget_data["cat1_id"], 1200.0)

        result = svc.get_all_with_spending()
        b = result[0]
        assert b["spent"] == 1200.0
        assert b["remaining"] == -200.0
        assert b["percentage"] == 120.0
        assert b["status"] == "red"

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
        assert result[0]["spent"] == 0.0


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
        svc = _svc(budget_data["user_id"])
        result = svc.create(budget_data["cat1_id"], 1000.0, "")

        assert result["currency"] == "EGP"

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
        inst_id = str(uuid.uuid4())
        acct_id = str(uuid.uuid4())
        tx_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO institutions (id, user_id, name, type)"
                " VALUES (%s, %s, 'TestInst', 'bank')"
                " ON CONFLICT DO NOTHING",
                [inst_id, budget_data["user_id"]],
            )
            cursor.execute(
                "INSERT INTO accounts (id, user_id, institution_id, name, type, currency,"
                " current_balance, initial_balance)"
                " VALUES (%s, %s, %s, 'Test', 'savings', 'EGP', 0, 0)",
                [acct_id, budget_data["user_id"], inst_id],
            )
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, category_id, type,"
                " amount, currency, date, balance_delta)"
                " VALUES (%s, %s, %s, %s, 'income', %s, 'EGP', %s, %s)",
                [
                    tx_id,
                    budget_data["user_id"],
                    acct_id,
                    budget_data["cat1_id"],
                    500.0,
                    date.today(),
                    500.0,
                ],
            )

        result = svc.get_all_with_spending()
        assert len(result) == 1
        b = result[0]
        # Income transactions don't count as spending — spent is 0
        assert b["spent"] == 0.0
        assert b["percentage"] == 0.0
        assert b["status"] == "green"

    def test_zero_limit_budget_percentage(self, budget_data: dict) -> None:
        """Budget with monthly_limit=0 is rejected by create validation."""
        svc = _svc(budget_data["user_id"])
        # The service rejects monthly_limit <= 0, so zero-limit cannot be created
        with pytest.raises(ValueError, match="Monthly limit must be positive"):
            svc.create(budget_data["cat1_id"], 0.0, "EGP")


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

    Creates a temporary account if needed, then inserts a transaction.
    """
    if tx_date is None:
        tx_date = date.today()

    inst_id = str(uuid.uuid4())
    acct_id = str(uuid.uuid4())
    tx_id = str(uuid.uuid4())

    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO institutions (id, user_id, name, type)"
            " VALUES (%s, %s, 'TestInst', 'bank')"
            " ON CONFLICT DO NOTHING",
            [inst_id, user_id],
        )
        cursor.execute(
            "INSERT INTO accounts (id, user_id, institution_id, name, type, currency,"
            " current_balance, initial_balance)"
            " VALUES (%s, %s, %s, 'Test', 'savings',"
            " 'EGP', 0, 0)",
            [acct_id, user_id, inst_id],
        )
        cursor.execute(
            "INSERT INTO transactions (id, user_id, account_id, category_id, type,"
            " amount, currency, date, balance_delta)"
            " VALUES (%s, %s, %s, %s, 'expense', %s, 'EGP', %s, %s)",
            [tx_id, user_id, acct_id, category_id, amount, tx_date, -amount],
        )
