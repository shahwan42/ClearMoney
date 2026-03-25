"""
Investment service tests — CRUD + validation for portfolio tracking.

Tests run against the real database with --reuse-db. Verifies create, update, delete,
total valuation, and input validation.
"""

from zoneinfo import ZoneInfo

import pytest
from django.db import connection

from conftest import SessionFactory, UserFactory
from core.models import Session, User
from investments.services import InvestmentService

TZ = ZoneInfo("Africa/Cairo")


@pytest.fixture
def inv_data(db: object):  # noqa: ARG001
    """User for investment tests. Cleans up investments on teardown."""
    user = UserFactory()
    SessionFactory(user=user)
    user_id = str(user.id)

    yield {"user_id": user_id}

    # Cleanup
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM investments WHERE user_id = %s", [user_id])
    Session.objects.filter(user_id=user_id).delete()
    User.objects.filter(id=user_id).delete()


def _svc(user_id: str) -> InvestmentService:
    return InvestmentService(user_id, TZ)


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCreate:
    def test_creates_investment(self, inv_data: dict) -> None:
        svc = _svc(inv_data["user_id"])
        new_id = svc.create({"fund_name": "AZG", "units": 100, "unit_price": 10.5})
        assert new_id

        investments = svc.get_all()
        assert len(investments) == 1
        assert investments[0]["fund_name"] == "AZG"
        assert investments[0]["units"] == 100.0
        assert investments[0]["last_unit_price"] == 10.5

    def test_defaults_platform_and_currency(self, inv_data: dict) -> None:
        svc = _svc(inv_data["user_id"])
        svc.create({"fund_name": "BMF", "units": 50, "unit_price": 20})

        investments = svc.get_all()
        assert investments[0]["platform"] == "Thndr"
        assert investments[0]["currency"] == "EGP"

    def test_custom_platform_and_currency(self, inv_data: dict) -> None:
        svc = _svc(inv_data["user_id"])
        svc.create(
            {
                "fund_name": "VTI",
                "units": 10,
                "unit_price": 250,
                "platform": "EFG Hermes",
                "currency": "USD",
            }
        )

        investments = svc.get_all()
        assert investments[0]["platform"] == "EFG Hermes"
        assert investments[0]["currency"] == "USD"

    def test_empty_fund_name_raises(self, inv_data: dict) -> None:
        svc = _svc(inv_data["user_id"])
        with pytest.raises(ValueError, match="Fund name"):
            svc.create({"fund_name": "", "units": 10, "unit_price": 10})

    def test_zero_units_raises(self, inv_data: dict) -> None:
        svc = _svc(inv_data["user_id"])
        with pytest.raises(ValueError, match="Units"):
            svc.create({"fund_name": "AZG", "units": 0, "unit_price": 10})

    def test_negative_price_raises(self, inv_data: dict) -> None:
        svc = _svc(inv_data["user_id"])
        with pytest.raises(ValueError, match="Unit price"):
            svc.create({"fund_name": "AZG", "units": 10, "unit_price": -5})


# ---------------------------------------------------------------------------
# Get all + valuation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGetAll:
    def test_returns_sorted_by_platform_fund(self, inv_data: dict) -> None:
        svc = _svc(inv_data["user_id"])
        svc.create({"fund_name": "ZZZ", "units": 10, "unit_price": 1, "platform": "B"})
        svc.create({"fund_name": "AAA", "units": 10, "unit_price": 1, "platform": "A"})
        svc.create({"fund_name": "BBB", "units": 10, "unit_price": 1, "platform": "A"})

        investments = svc.get_all()
        names = [i["fund_name"] for i in investments]
        assert names == ["AAA", "BBB", "ZZZ"]

    def test_includes_computed_valuation(self, inv_data: dict) -> None:
        svc = _svc(inv_data["user_id"])
        svc.create({"fund_name": "AZG", "units": 152.347, "unit_price": 10.5})

        investments = svc.get_all()
        expected = 152.347 * 10.5
        assert abs(investments[0]["valuation"] - expected) < 0.01

    def test_empty_portfolio(self, inv_data: dict) -> None:
        svc = _svc(inv_data["user_id"])
        assert svc.get_all() == []


# ---------------------------------------------------------------------------
# Total valuation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTotalValuation:
    def test_sums_all_investments(self, inv_data: dict) -> None:
        svc = _svc(inv_data["user_id"])
        svc.create({"fund_name": "A", "units": 100, "unit_price": 10})  # 1000
        svc.create({"fund_name": "B", "units": 50, "unit_price": 20})  # 1000

        total = svc.get_total_valuation()
        assert total == 2000.0

    def test_empty_portfolio_returns_zero(self, inv_data: dict) -> None:
        svc = _svc(inv_data["user_id"])
        assert svc.get_total_valuation() == 0.0


# ---------------------------------------------------------------------------
# Update valuation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestUpdateValuation:
    def test_updates_unit_price(self, inv_data: dict) -> None:
        svc = _svc(inv_data["user_id"])
        inv_id = svc.create({"fund_name": "AZG", "units": 100, "unit_price": 10})

        svc.update_valuation(inv_id, 15.0)

        investments = svc.get_all()
        assert investments[0]["last_unit_price"] == 15.0
        assert investments[0]["valuation"] == 1500.0

    def test_total_recalculates_after_update(self, inv_data: dict) -> None:
        svc = _svc(inv_data["user_id"])
        inv_id = svc.create({"fund_name": "AZG", "units": 100, "unit_price": 10})

        svc.update_valuation(inv_id, 20.0)
        assert svc.get_total_valuation() == 2000.0

    def test_zero_price_raises(self, inv_data: dict) -> None:
        svc = _svc(inv_data["user_id"])
        inv_id = svc.create({"fund_name": "AZG", "units": 100, "unit_price": 10})

        with pytest.raises(ValueError, match="Unit price"):
            svc.update_valuation(inv_id, 0)


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDelete:
    def test_removes_investment(self, inv_data: dict) -> None:
        svc = _svc(inv_data["user_id"])
        inv_id = svc.create({"fund_name": "AZG", "units": 100, "unit_price": 10})

        svc.delete(inv_id)

        assert len(svc.get_all()) == 0
        assert svc.get_total_valuation() == 0.0


# ---------------------------------------------------------------------------
# Valuation edge cases
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestInvestmentValuationEdgeCases:
    """Monetary edge cases: very small prices and large value products."""

    def test_very_small_unit_price(self, inv_data: dict) -> None:
        """A fractional unit price (0.001) is stored and retrieved correctly."""
        svc = _svc(inv_data["user_id"])
        inv_id = svc.create(
            {"fund_name": "MicroFund", "units": 1000, "unit_price": 0.001}
        )

        investments = svc.get_all()
        match = [i for i in investments if i["id"] == inv_id]
        assert len(match) == 1
        assert match[0]["last_unit_price"] == 0.001

    def test_large_units_times_large_price(self, inv_data: dict) -> None:
        """Large units * large price computes without DB overflow.

        999999 * 999.99 = 999,990,000.01 — fits within NUMERIC(15,2).
        """
        svc = _svc(inv_data["user_id"])
        svc.create({"fund_name": "BigFund", "units": 999999, "unit_price": 999.99})

        investments = svc.get_all()
        assert len(investments) == 1
        expected = 999999 * 999.99
        assert abs(investments[0]["valuation"] - expected) < 0.01

        # Also verify get_total_valuation aggregates correctly
        total = svc.get_total_valuation()
        assert abs(total - expected) < 0.01
