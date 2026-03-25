"""
Exchange rate view tests — HTTP-level tests for /exchange-rates endpoint.

Tests page load, content rendering, and auth redirect.
Uses authenticated test client with session cookie.
"""

from datetime import date
from typing import Any

import pytest
from django.test import Client

from conftest import SessionFactory, UserFactory, set_auth_cookie
from core.models import ExchangeRateLog
from tests.factories import ExchangeRateLogFactory


@pytest.fixture
def er_view_data(db: object) -> Any:  # noqa: ARG001
    """User + session + a test exchange rate for view tests. Cleanup via rollback."""
    user = UserFactory()
    session = SessionFactory(user=user)

    # Create a test exchange rate (global data, no user_id)
    rate = ExchangeRateLogFactory(
        date=date.today(), rate="50.75", source="CBE", note="Test rate"
    )

    yield {
        "user_id": str(user.id),
        "session_token": session.token,
        "rate_ids": [str(rate.id)],
    }


# ---------------------------------------------------------------------------
# GET /exchange-rates — page load
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestExchangeRatesPage:
    def test_200(self, client: Client, er_view_data: dict[str, Any]) -> None:
        c = set_auth_cookie(client, er_view_data["session_token"])
        response = c.get("/exchange-rates")
        assert response.status_code == 200
        assert b"Exchange Rate History" in response.content

    def test_shows_rate(self, client: Client, er_view_data: dict[str, Any]) -> None:
        c = set_auth_cookie(client, er_view_data["session_token"])
        response = c.get("/exchange-rates")
        assert b"50.75" in response.content
        assert b"CBE" in response.content

    def test_empty_state(self, client: Client, er_view_data: dict[str, Any]) -> None:
        """When no rates exist, shows empty state message."""
        # Delete all rates for this test, then check empty state
        ExchangeRateLog.objects.all().delete()

        c = set_auth_cookie(client, er_view_data["session_token"])
        response = c.get("/exchange-rates")
        assert b"No exchange rates recorded yet" in response.content

    def test_unauthenticated_redirects(self, client: Client) -> None:
        response = client.get("/exchange-rates")
        assert response.status_code == 302
        assert "/login" in response.url  # type: ignore[attr-defined]
