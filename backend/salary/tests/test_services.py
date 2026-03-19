"""
Salary service tests — distribute salary with income, exchange, and transfers.

Port of Go's internal/service/salary_test.go. Tests run against the real database
with --reuse-db (Go owns schema). Verifies atomicity, balance updates, and validation.
"""

from datetime import date
from zoneinfo import ZoneInfo

import pytest
from django.db import connection

from conftest import SessionFactory, UserFactory
from core.models import Session, User
from salary.services import SalaryAllocation, SalaryDistribution, SalaryService
from tests.factories import AccountFactory, InstitutionFactory

TZ = ZoneInfo("Africa/Cairo")


@pytest.fixture
def salary_data(db: object):  # noqa: ARG001
    """User + institution + USD account + EGP main account + EGP savings account."""
    user = UserFactory()
    SessionFactory(user=user)
    user_id = str(user.id)

    inst = InstitutionFactory(user_id=user.id)

    usd_acct = AccountFactory(
        user_id=user.id,
        institution_id=inst.id,
        name="USD Salary",
        type="current",
        currency="USD",
        current_balance=0,
        initial_balance=0,
    )
    egp_main = AccountFactory(
        user_id=user.id,
        institution_id=inst.id,
        name="Main EGP",
        type="current",
        currency="EGP",
        current_balance=0,
        initial_balance=0,
    )
    egp_savings = AccountFactory(
        user_id=user.id,
        institution_id=inst.id,
        name="Savings",
        type="savings",
        currency="EGP",
        current_balance=0,
        initial_balance=0,
    )

    yield {
        "user_id": user_id,
        "usd_account_id": str(usd_acct.id),
        "egp_account_id": str(egp_main.id),
        "savings_account_id": str(egp_savings.id),
    }

    # Cleanup — order matters for FK constraints
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM transactions WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM accounts WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM institutions WHERE user_id = %s", [user_id])
    Session.objects.filter(user_id=user_id).delete()
    User.objects.filter(id=user_id).delete()


def _svc(user_id: str) -> SalaryService:
    return SalaryService(user_id, TZ)


def _get_balance(account_id: str) -> float:
    """Helper to read current_balance for an account."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT current_balance FROM accounts WHERE id = %s", [account_id]
        )
        row = cursor.fetchone()
        return float(row[0]) if row else 0.0


def _count_transactions(user_id: str) -> int:
    """Count all transactions for a user."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM transactions WHERE user_id = %s", [user_id]
        )
        row = cursor.fetchone()
        return int(row[0]) if row else 0


# ---------------------------------------------------------------------------
# Basic distribution (no allocations)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDistributeBasic:
    def test_creates_income_and_exchange(self, salary_data: dict) -> None:
        """Salary with no allocations: 1 income + 2 exchange = 3 transactions."""
        svc = _svc(salary_data["user_id"])
        dist = SalaryDistribution(
            salary_usd=1000.0,
            exchange_rate=50.0,
            usd_account_id=salary_data["usd_account_id"],
            egp_account_id=salary_data["egp_account_id"],
            allocations=[],
            tx_date=date(2026, 3, 15),
        )

        result = svc.distribute(dist)

        assert result.salary_usd == 1000.0
        assert result.exchange_rate == 50.0
        assert result.salary_egp == 50000.0
        assert result.alloc_count == 0

        # 3 transactions: 1 income + 2 exchange (linked pair)
        assert _count_transactions(salary_data["user_id"]) == 3

        # USD account: +1000 (income) - 1000 (exchange) = 0
        assert _get_balance(salary_data["usd_account_id"]) == 0.0

        # EGP account: +50000 (exchange credit)
        assert _get_balance(salary_data["egp_account_id"]) == 50000.0


# ---------------------------------------------------------------------------
# Distribution with allocations
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDistributeWithAllocations:
    def test_creates_income_exchange_and_transfers(self, salary_data: dict) -> None:
        """Salary with 1 allocation: 1 income + 2 exchange + 2 transfer = 5 tx."""
        svc = _svc(salary_data["user_id"])
        dist = SalaryDistribution(
            salary_usd=1000.0,
            exchange_rate=50.0,
            usd_account_id=salary_data["usd_account_id"],
            egp_account_id=salary_data["egp_account_id"],
            allocations=[
                SalaryAllocation(
                    account_id=salary_data["savings_account_id"],
                    amount=10000.0,
                    note="Savings",
                ),
            ],
            tx_date=date(2026, 3, 15),
        )

        result = svc.distribute(dist)

        assert result.alloc_count == 1

        # 5 transactions: 1 income + 2 exchange + 2 transfer
        assert _count_transactions(salary_data["user_id"]) == 5

        # USD: +1000 - 1000 = 0
        assert _get_balance(salary_data["usd_account_id"]) == 0.0

        # EGP main: +50000 (exchange) - 10000 (transfer) = 40000
        assert _get_balance(salary_data["egp_account_id"]) == 40000.0

        # Savings: +10000
        assert _get_balance(salary_data["savings_account_id"]) == 10000.0

    def test_multiple_allocations(self, salary_data: dict) -> None:
        """Two allocations from the same salary."""
        svc = _svc(salary_data["user_id"])
        dist = SalaryDistribution(
            salary_usd=2000.0,
            exchange_rate=50.0,
            usd_account_id=salary_data["usd_account_id"],
            egp_account_id=salary_data["egp_account_id"],
            allocations=[
                SalaryAllocation(
                    account_id=salary_data["savings_account_id"],
                    amount=20000.0,
                ),
                SalaryAllocation(
                    account_id=salary_data["savings_account_id"],
                    amount=10000.0,
                ),
            ],
            tx_date=date(2026, 3, 15),
        )

        result = svc.distribute(dist)

        assert result.alloc_count == 2

        # EGP main: +100000 - 20000 - 10000 = 70000
        assert _get_balance(salary_data["egp_account_id"]) == 70000.0

        # Savings: +20000 + 10000 = 30000
        assert _get_balance(salary_data["savings_account_id"]) == 30000.0


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestValidation:
    def test_negative_salary(self, salary_data: dict) -> None:
        svc = _svc(salary_data["user_id"])
        dist = SalaryDistribution(
            salary_usd=0.0,
            exchange_rate=50.0,
            usd_account_id=salary_data["usd_account_id"],
            egp_account_id=salary_data["egp_account_id"],
            allocations=[],
        )
        with pytest.raises(ValueError, match="positive"):
            svc.distribute(dist)

    def test_negative_rate(self, salary_data: dict) -> None:
        svc = _svc(salary_data["user_id"])
        dist = SalaryDistribution(
            salary_usd=1000.0,
            exchange_rate=-1.0,
            usd_account_id=salary_data["usd_account_id"],
            egp_account_id=salary_data["egp_account_id"],
            allocations=[],
        )
        with pytest.raises(ValueError, match="positive"):
            svc.distribute(dist)

    def test_missing_usd_account(self, salary_data: dict) -> None:
        svc = _svc(salary_data["user_id"])
        dist = SalaryDistribution(
            salary_usd=1000.0,
            exchange_rate=50.0,
            usd_account_id="",
            egp_account_id=salary_data["egp_account_id"],
            allocations=[],
        )
        with pytest.raises(ValueError, match="account"):
            svc.distribute(dist)

    def test_missing_egp_account(self, salary_data: dict) -> None:
        svc = _svc(salary_data["user_id"])
        dist = SalaryDistribution(
            salary_usd=1000.0,
            exchange_rate=50.0,
            usd_account_id=salary_data["usd_account_id"],
            egp_account_id="",
            allocations=[],
        )
        with pytest.raises(ValueError, match="account"):
            svc.distribute(dist)

    def test_allocations_exceed_salary(self, salary_data: dict) -> None:
        svc = _svc(salary_data["user_id"])
        dist = SalaryDistribution(
            salary_usd=100.0,
            exchange_rate=50.0,
            usd_account_id=salary_data["usd_account_id"],
            egp_account_id=salary_data["egp_account_id"],
            allocations=[
                SalaryAllocation(
                    account_id=salary_data["savings_account_id"],
                    amount=6000.0,  # > 5000 EGP salary
                ),
            ],
        )
        with pytest.raises(ValueError, match="exceed"):
            svc.distribute(dist)


# ---------------------------------------------------------------------------
# Atomicity
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAtomicity:
    def test_rollback_on_transfer_failure(self, salary_data: dict) -> None:
        """If an allocation transfer fails, no transactions should exist."""
        svc = _svc(salary_data["user_id"])
        dist = SalaryDistribution(
            salary_usd=1000.0,
            exchange_rate=50.0,
            usd_account_id=salary_data["usd_account_id"],
            egp_account_id=salary_data["egp_account_id"],
            allocations=[
                SalaryAllocation(
                    account_id="00000000-0000-0000-0000-000000000000",  # nonexistent
                    amount=10000.0,
                ),
            ],
        )

        with pytest.raises(Exception):
            svc.distribute(dist)

        # No transactions should have been created (rollback)
        assert _count_transactions(salary_data["user_id"]) == 0

        # Balances should be unchanged
        assert _get_balance(salary_data["usd_account_id"]) == 0.0
        assert _get_balance(salary_data["egp_account_id"]) == 0.0
