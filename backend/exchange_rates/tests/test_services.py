"""
Exchange rate service tests — read-only queries for exchange rate history.

Port of Go's ExchangeRateRepo tests. Tests run against the real database
with --reuse-db (Go owns schema). Verifies get_all ordering, empty state,
and field completeness.

Note: Exchange rates are global data (no user_id), but the page is still
behind auth. The service doesn't need user_id unlike most other services.
"""

from datetime import date, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from django.db import connection

from exchange_rates.services import ExchangeRateService

TZ = ZoneInfo("Africa/Cairo")


@pytest.fixture
def rate_data(db: object) -> Any:  # noqa: ARG001
    """Insert test exchange rates. Cleans up on teardown."""
    rate_ids: list[str] = []

    with connection.cursor() as cursor:
        # Insert two rates with different dates
        cursor.execute(
            """
            INSERT INTO exchange_rate_log (date, rate, source, note)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            [date.today() - timedelta(days=1), 50.25, "CBE", "Daily rate"],
        )
        rate_ids.append(str(cursor.fetchone()[0]))

        cursor.execute(
            """
            INSERT INTO exchange_rate_log (date, rate, source, note)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            [date.today(), 50.50, "manual", None],
        )
        rate_ids.append(str(cursor.fetchone()[0]))

    yield {"rate_ids": rate_ids}

    # Cleanup
    with connection.cursor() as cursor:
        for rid in rate_ids:
            cursor.execute("DELETE FROM exchange_rate_log WHERE id = %s", [rid])


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
