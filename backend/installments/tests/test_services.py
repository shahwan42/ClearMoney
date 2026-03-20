"""
Installment service tests — CRUD + payment recording for installment plans.

Port of Go's internal/service/installment_test.go. Tests run against the real
database with --reuse-db (Go owns schema). Verifies create, auto-computed
monthly amount, record payment (with transaction creation), and delete.
"""

from typing import Any
from zoneinfo import ZoneInfo

import pytest
from django.db import connection

from conftest import SessionFactory, UserFactory
from core.models import Session, User
from installments.services import InstallmentService
from tests.factories import AccountFactory, InstitutionFactory

TZ = ZoneInfo("Africa/Cairo")


@pytest.fixture
def inst_data(db: object) -> Any:  # noqa: ARG001
    """User + account for installment tests.

    Creates a credit card account with E£100,000 balance (enough for payments).
    Cleans up installment_plans, transactions, accounts, institutions on teardown.
    """
    user = UserFactory()
    SessionFactory(user=user)
    user_id = str(user.id)
    inst = InstitutionFactory(user_id=user.id)
    account = AccountFactory(
        user_id=user.id,
        institution_id=inst.id,
        name="Credit Card",
        type="credit_card",
        currency="EGP",
        current_balance=0,
    )

    yield {
        "user_id": user_id,
        "account_id": str(account.id),
    }

    # Cleanup (FK ordering: transactions → installment_plans → accounts → institutions)
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM transactions WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM installment_plans WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM accounts WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM institutions WHERE user_id = %s", [user_id])
    Session.objects.filter(user_id=user_id).delete()
    User.objects.filter(id=user_id).delete()


def _svc(user_id: str) -> InstallmentService:
    return InstallmentService(user_id, TZ)


def _plan_data(account_id: str, **overrides: Any) -> dict[str, Any]:
    """Default plan data for tests."""
    data: dict[str, Any] = {
        "description": "iPhone 16 Pro",
        "total_amount": 60000,
        "num_installments": 12,
        "account_id": account_id,
        "start_date": "2026-01-15",
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCreate:
    def test_creates_plan(self, inst_data: dict[str, Any]) -> None:
        svc = _svc(inst_data["user_id"])
        plan_id = svc.create(_plan_data(inst_data["account_id"]))
        assert plan_id

        plans = svc.get_all()
        assert len(plans) == 1
        assert plans[0]["description"] == "iPhone 16 Pro"
        assert plans[0]["total_amount"] == 60000.0
        assert plans[0]["num_installments"] == 12

    def test_auto_computes_monthly_amount(self, inst_data: dict[str, Any]) -> None:
        svc = _svc(inst_data["user_id"])
        svc.create(_plan_data(inst_data["account_id"]))

        plans = svc.get_all()
        assert plans[0]["monthly_amount"] == 5000.0  # 60000 / 12

    def test_remaining_equals_num_on_create(self, inst_data: dict[str, Any]) -> None:
        svc = _svc(inst_data["user_id"])
        svc.create(_plan_data(inst_data["account_id"]))

        plans = svc.get_all()
        assert plans[0]["remaining_installments"] == 12
        assert plans[0]["paid_installments"] == 0
        assert plans[0]["is_complete"] is False

    def test_empty_description_raises(self, inst_data: dict[str, Any]) -> None:
        svc = _svc(inst_data["user_id"])
        with pytest.raises(ValueError, match="Description"):
            svc.create(_plan_data(inst_data["account_id"], description=""))

    def test_zero_total_raises(self, inst_data: dict[str, Any]) -> None:
        svc = _svc(inst_data["user_id"])
        with pytest.raises(ValueError, match="Total amount"):
            svc.create(_plan_data(inst_data["account_id"], total_amount=0))

    def test_zero_installments_raises(self, inst_data: dict[str, Any]) -> None:
        svc = _svc(inst_data["user_id"])
        with pytest.raises(ValueError, match="Number of installments"):
            svc.create(_plan_data(inst_data["account_id"], num_installments=0))

    def test_missing_account_raises(self, inst_data: dict[str, Any]) -> None:
        svc = _svc(inst_data["user_id"])
        with pytest.raises(ValueError, match="Account"):
            svc.create(_plan_data("", description="No Account Plan"))


# ---------------------------------------------------------------------------
# Get all
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGetAll:
    def test_ordered_by_remaining_desc(self, inst_data: dict[str, Any]) -> None:
        """Active plans (higher remaining) should appear first."""
        svc = _svc(inst_data["user_id"])
        # Create two plans with different remaining counts
        id1 = svc.create(
            _plan_data(
                inst_data["account_id"], description="Plan A", num_installments=3
            )
        )
        svc.create(
            _plan_data(
                inst_data["account_id"], description="Plan B", num_installments=12
            )
        )
        # Record a payment on Plan A to reduce its remaining
        svc.record_payment(id1)
        svc.record_payment(id1)

        plans = svc.get_all()
        # Plan B (12 remaining) should be before Plan A (1 remaining)
        assert plans[0]["description"] == "Plan B"
        assert plans[1]["description"] == "Plan A"

    def test_empty_returns_empty_list(self, inst_data: dict[str, Any]) -> None:
        svc = _svc(inst_data["user_id"])
        assert svc.get_all() == []

    def test_includes_computed_fields(self, inst_data: dict[str, Any]) -> None:
        svc = _svc(inst_data["user_id"])
        svc.create(_plan_data(inst_data["account_id"]))

        plans = svc.get_all()
        assert "is_complete" in plans[0]
        assert "paid_installments" in plans[0]


# ---------------------------------------------------------------------------
# Record payment
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRecordPayment:
    def test_decrements_remaining(self, inst_data: dict[str, Any]) -> None:
        svc = _svc(inst_data["user_id"])
        plan_id = svc.create(_plan_data(inst_data["account_id"]))

        svc.record_payment(plan_id)

        plan = svc.get_by_id(plan_id)
        assert plan["remaining_installments"] == 11
        assert plan["paid_installments"] == 1

    def test_creates_expense_transaction(self, inst_data: dict[str, Any]) -> None:
        svc = _svc(inst_data["user_id"])
        plan_id = svc.create(_plan_data(inst_data["account_id"]))

        svc.record_payment(plan_id)

        # Verify a transaction was created
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT type, amount, note FROM transactions WHERE user_id = %s ORDER BY created_at DESC LIMIT 1",
                [inst_data["user_id"]],
            )
            row = cursor.fetchone()

        assert row is not None
        assert row[0] == "expense"
        assert float(row[1]) == 5000.0
        assert "Installment 1/12" in row[2]
        assert "iPhone 16 Pro" in row[2]

    def test_fully_paid_raises(self, inst_data: dict[str, Any]) -> None:
        svc = _svc(inst_data["user_id"])
        # Create a plan with only 1 installment
        plan_id = svc.create(
            _plan_data(inst_data["account_id"], num_installments=1, total_amount=1000)
        )
        svc.record_payment(plan_id)

        with pytest.raises(ValueError, match="fully paid"):
            svc.record_payment(plan_id)


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDelete:
    def test_removes_plan(self, inst_data: dict[str, Any]) -> None:
        svc = _svc(inst_data["user_id"])
        plan_id = svc.create(_plan_data(inst_data["account_id"]))

        svc.delete(plan_id)

        assert len(svc.get_all()) == 0
