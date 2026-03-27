"""
Investment view tests — HTTP-level tests for /investments* endpoints.

Tests page load, add, update valuation, delete, and auth redirects.
Uses authenticated test client with session cookie.
"""

from typing import Any

import pytest
from django.test import Client

from conftest import SessionFactory, UserFactory, set_auth_cookie
from investments.models import Investment


@pytest.fixture
def inv_view_data(db: object):  # noqa: ARG001
    """User + session for view tests. Cleanup is automatic via pytest-django rollback."""
    user = UserFactory()
    session = SessionFactory(user=user)

    yield {
        "user_id": str(user.id),
        "session_token": session.token,
    }


def _create_investment(client: Client, token: str) -> None:
    """Helper to create a test investment via the add endpoint."""
    c = set_auth_cookie(client, token)
    c.post(
        "/investments/add",
        {
            "platform": "Thndr",
            "fund_name": "TestFund",
            "units": "100",
            "unit_price": "10.5",
            "currency": "EGP",
        },
    )


# ---------------------------------------------------------------------------
# GET /investments — page load
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestInvestmentsPage:
    def test_200(self, client: Client, inv_view_data: dict[str, Any]) -> None:
        c = set_auth_cookie(client, inv_view_data["session_token"])
        response = c.get("/investments")
        assert response.status_code == 200
        assert b"Investment Portfolio" in response.content

    def test_empty_state(self, client: Client, inv_view_data: dict[str, Any]) -> None:
        c = set_auth_cookie(client, inv_view_data["session_token"])
        response = c.get("/investments")
        assert b"No investments yet." in response.content

    def test_shows_investment(
        self, client: Client, inv_view_data: dict[str, Any]
    ) -> None:
        _create_investment(client, inv_view_data["session_token"])
        c = set_auth_cookie(client, inv_view_data["session_token"])
        response = c.get("/investments")
        assert b"TestFund" in response.content
        assert b"Thndr" in response.content

    def test_unauthenticated_redirects(self, client: Client) -> None:
        response = client.get("/investments")
        assert response.status_code == 302
        assert "/login" in response.url  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# POST /investments/add — create investment
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestInvestmentAdd:
    def test_creates_and_redirects(
        self, client: Client, inv_view_data: dict[str, Any]
    ) -> None:
        c = set_auth_cookie(client, inv_view_data["session_token"])
        response = c.post(
            "/investments/add",
            {
                "platform": "Thndr",
                "fund_name": "AZG",
                "units": "50",
                "unit_price": "12.5",
                "currency": "EGP",
            },
        )
        # htmx_redirect returns 200 with HX-Redirect header for HTMX,
        # or 302 redirect for standard POST
        assert response.status_code in (200, 302)

        # Verify investment was created
        c2 = set_auth_cookie(client, inv_view_data["session_token"])
        page = c2.get("/investments")
        assert b"AZG" in page.content

    def test_missing_fund_name_returns_400(
        self, client: Client, inv_view_data: dict[str, Any]
    ) -> None:
        c = set_auth_cookie(client, inv_view_data["session_token"])
        response = c.post(
            "/investments/add",
            {"platform": "Thndr", "fund_name": "", "units": "10", "unit_price": "10"},
        )
        assert response.status_code == 400

    def test_zero_units_returns_400(
        self, client: Client, inv_view_data: dict[str, Any]
    ) -> None:
        c = set_auth_cookie(client, inv_view_data["session_token"])
        response = c.post(
            "/investments/add",
            {"fund_name": "AZG", "units": "0", "unit_price": "10"},
        )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# POST /investments/<id>/update — update unit price
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestInvestmentUpdate:
    def test_updates_price(self, client: Client, inv_view_data: dict[str, Any]) -> None:
        _create_investment(client, inv_view_data["session_token"])

        # Get the investment ID via ORM
        inv_id = (
            Investment.objects.filter(user_id=inv_view_data["user_id"])
            .values_list("id", flat=True)
            .first()
        )

        c = set_auth_cookie(client, inv_view_data["session_token"])
        response = c.post(
            f"/investments/{inv_id}/update",
            {"unit_price": "15.0"},
        )
        assert response.status_code in (200, 302)

        # Verify price was updated
        c2 = set_auth_cookie(client, inv_view_data["session_token"])
        page = c2.get("/investments")
        assert b"15.0000" in page.content

    def test_zero_price_returns_400(
        self, client: Client, inv_view_data: dict[str, Any]
    ) -> None:
        _create_investment(client, inv_view_data["session_token"])

        inv_id = (
            Investment.objects.filter(user_id=inv_view_data["user_id"])
            .values_list("id", flat=True)
            .first()
        )

        c = set_auth_cookie(client, inv_view_data["session_token"])
        response = c.post(
            f"/investments/{inv_id}/update",
            {"unit_price": "0"},
        )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /investments/<id>/delete — remove investment
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestInvestmentDelete:
    def test_deletes_investment(
        self, client: Client, inv_view_data: dict[str, Any]
    ) -> None:
        _create_investment(client, inv_view_data["session_token"])

        inv_id = (
            Investment.objects.filter(user_id=inv_view_data["user_id"])
            .values_list("id", flat=True)
            .first()
        )

        c = set_auth_cookie(client, inv_view_data["session_token"])
        response = c.delete(f"/investments/{inv_id}/delete")
        assert response.status_code in (200, 302)

        # Verify investment was deleted
        c2 = set_auth_cookie(client, inv_view_data["session_token"])
        page = c2.get("/investments")
        assert b"No investments yet." in page.content
