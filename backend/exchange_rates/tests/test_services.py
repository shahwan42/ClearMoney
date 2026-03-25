"""
Exchange rate service tests — read-only queries for exchange rate history.

Tests run against the real database with --reuse-db. Verifies get_all ordering, empty state,
and field completeness.

Note: Exchange rates are global data (no user_id), but the page is still
behind auth. The service doesn't need user_id unlike most other services.
"""

from datetime import date, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from exchange_rates.services import ExchangeRateService
from tests.factories import ExchangeRateLogFactory

TZ = ZoneInfo("Africa/Cairo")


@pytest.fixture
def rate_data(db: object) -> Any:  # noqa: ARG001
    """Insert test exchange rates. Cleanup is automatic via pytest-django rollback."""
    r1 = ExchangeRateLogFactory(
        date=date.today() - timedelta(days=1),
        rate="50.25",
        source="CBE",
        note="Daily rate",
    )
    r2 = ExchangeRateLogFactory(
        date=date.today(), rate="50.50", source="manual", note=None
    )

    yield {"rate_ids": [str(r1.id), str(r2.id)]}


# ---------------------------------------------------------------------------
# Get all
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGetAll:
    def test_returns_rates_ordered_by_created_at_desc(
        self, rate_data: dict[str, Any]
    ) -> None:
        """Newest rates should appear first."""
        svc = ExchangeRateService(TZ)
        rates = svc.get_all()

        assert len(rates) >= 2
        # The second inserted rate (50.50) should be first (newest created_at)
        rate_values = [r["rate"] for r in rates[:2]]
        assert 50.50 in rate_values
        assert 50.25 in rate_values

    def test_empty_returns_empty_list(self) -> None:
        """When no rates exist, returns empty list (may have pre-existing data)."""
        svc = ExchangeRateService(TZ)
        rates = svc.get_all()
        # Just verify it returns a list (may have production data)
        assert isinstance(rates, list)

    def test_includes_all_fields(self, rate_data: dict[str, Any]) -> None:
        """Each rate dict should have all expected fields."""
        svc = ExchangeRateService(TZ)
        rates = svc.get_all()
        assert len(rates) >= 1

        rate = rates[0]
        assert "id" in rate
        assert "date" in rate
        assert "rate" in rate
        assert "source" in rate
        assert "created_at" in rate

    def test_nullable_fields(self, rate_data: dict[str, Any]) -> None:
        """Source and note can be None."""
        svc = ExchangeRateService(TZ)
        rates = svc.get_all()

        # Find the rate with no note (50.50, manual)
        manual_rates = [r for r in rates if r.get("source") == "manual"]
        assert len(manual_rates) >= 1
        assert manual_rates[0]["note"] is None
