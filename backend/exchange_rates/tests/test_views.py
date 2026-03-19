"""
Exchange rate view tests — HTTP-level tests for /exchange-rates endpoint.

Tests page load, content rendering, and auth redirect.
Uses authenticated test client with session cookie.
"""

from datetime import date
from typing import Any

import pytest
from django.db import connection
from django.test import Client

from conftest import SessionFactory, UserFactory
from core.middleware import COOKIE_NAME
from core.models import Session, User


@pytest.fixture
def er_view_data(db: object) -> Any:  # noqa: ARG001
    """User + session + a test exchange rate for view tests."""
    user = UserFactory()
    session = SessionFactory(user=user)
    user_id = str(user.id)

    # Insert a test exchange rate (global data, no user_id)
    rate_ids: list[str] = []
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO exchange_rate_log (date, rate, source, note)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            [date.today(), 50.75, "CBE", "Test rate"],
        )
        rate_ids.append(str(cursor.fetchone()[0]))

    yield {
        "user_id": user_id,
        "session_token": session.token,
        "rate_ids": rate_ids,
    }

    # Cleanup
    with connection.cursor() as cursor:
        for rid in rate_ids:
            cursor.execute("DELETE FROM exchange_rate_log WHERE id = %s", [rid])
    Session.objects.filter(user_id=user_id).delete()
    User.objects.filter(id=user_id).delete()


def _auth_client(client: Client, token: str) -> Client:
    """Return an authenticated test client."""
    client.cookies[COOKIE_NAME] = token
    return client


# ---------------------------------------------------------------------------
# GET /exchange-rates — page load
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestExchangeRatesPage:
    def test_200(self, client: Client, er_view_data: dict[str, Any]) -> None:
        c = _auth_client(client, er_view_data["session_token"])
        response = c.get("/exchange-rates")
        assert response.status_code == 200
        assert b"Exchange Rate History" in response.content

    def test_shows_rate(self, client: Client, er_view_data: dict[str, Any]) -> None:
        c = _auth_client(client, er_view_data["session_token"])
        response = c.get("/exchange-rates")
        assert b"50.75" in response.content
        assert b"CBE" in response.content

    def test_empty_state(self, client: Client, er_view_data: dict[str, Any]) -> None:
        """When no rates exist, shows empty state message."""
        # Save existing rates, clear table, test, then restore
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, date, rate, source, note FROM exchange_rate_log"
            )
            saved_rows = cursor.fetchall()
            cursor.execute("DELETE FROM exchange_rate_log")

        er_view_data["rate_ids"].clear()

        try:
            c = _auth_client(client, er_view_data["session_token"])
            response = c.get("/exchange-rates")
            assert b"No exchange rates recorded yet" in response.content
        finally:
            # Restore saved rates
            with connection.cursor() as cursor:
                for row in saved_rows:
                    cursor.execute(
                        """
                        INSERT INTO exchange_rate_log (id, date, rate, source, note)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        list(row),
                    )

    def test_unauthenticated_redirects(self, client: Client) -> None:
        response = client.get("/exchange-rates")
        assert response.status_code == 302
        assert "/login" in response.url  # type: ignore[attr-defined]
