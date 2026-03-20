"""
Salary wizard view tests — HTTP-level tests for /salary* endpoints.

Tests the multi-step HTMX wizard flow: page load, step progression,
and final confirmation. Uses authenticated test client with session cookie.
"""

from typing import Any

import pytest
from django.db import connection
from django.test import Client

from conftest import SessionFactory, UserFactory, set_auth_cookie
from core.models import Session, User
from tests.factories import AccountFactory, InstitutionFactory


@pytest.fixture
def salary_view_data(db: object):  # noqa: ARG001
    """User + session + institution + USD/EGP accounts for view tests."""
    user = UserFactory()
    session = SessionFactory(user=user)
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
        "session_token": session.token,
        "usd_account_id": str(usd_acct.id),
        "egp_account_id": str(egp_main.id),
        "savings_account_id": str(egp_savings.id),
    }

    # Cleanup
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM transactions WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM accounts WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM institutions WHERE user_id = %s", [user_id])
    Session.objects.filter(user_id=user_id).delete()
    User.objects.filter(id=user_id).delete()


# ---------------------------------------------------------------------------
# GET /salary — page load
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSalaryPage:
    def test_200(self, client: Client, salary_view_data: dict[str, Any]) -> None:
        c = set_auth_cookie(client, salary_view_data["session_token"])
        response = c.get("/salary")
        assert response.status_code == 200
        assert b"Salary Distribution" in response.content

    def test_shows_usd_account(
        self, client: Client, salary_view_data: dict[str, Any]
    ) -> None:
        c = set_auth_cookie(client, salary_view_data["session_token"])
        response = c.get("/salary")
        assert b"USD Salary" in response.content

    def test_shows_egp_account(
        self, client: Client, salary_view_data: dict[str, Any]
    ) -> None:
        c = set_auth_cookie(client, salary_view_data["session_token"])
        response = c.get("/salary")
        assert b"Main EGP" in response.content

    def test_shows_salary_input(
        self, client: Client, salary_view_data: dict[str, Any]
    ) -> None:
        c = set_auth_cookie(client, salary_view_data["session_token"])
        response = c.get("/salary")
        assert b'name="salary_usd"' in response.content

    def test_unauthenticated_redirects(self, client: Client) -> None:
        response = client.get("/salary")
        assert response.status_code == 302
        assert "/login" in response.url  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# POST /salary/step2 — exchange rate form
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSalaryStep2:
    def test_returns_exchange_rate_form(
        self, client: Client, salary_view_data: dict[str, Any]
    ) -> None:
        c = set_auth_cookie(client, salary_view_data["session_token"])
        response = c.post(
            "/salary/step2",
            {
                "salary_usd": "3000",
                "usd_account_id": salary_view_data["usd_account_id"],
                "egp_account_id": salary_view_data["egp_account_id"],
                "date": "2026-03-15",
            },
        )
        assert response.status_code == 200
        assert b'name="exchange_rate"' in response.content
        assert b"3000" in response.content

    def test_invalid_salary_returns_400(
        self, client: Client, salary_view_data: dict[str, Any]
    ) -> None:
        c = set_auth_cookie(client, salary_view_data["session_token"])
        response = c.post(
            "/salary/step2",
            {"salary_usd": "0", "usd_account_id": "", "egp_account_id": ""},
        )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# POST /salary/step3 — allocation form
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSalaryStep3:
    def test_returns_allocation_form(
        self, client: Client, salary_view_data: dict[str, Any]
    ) -> None:
        c = set_auth_cookie(client, salary_view_data["session_token"])
        response = c.post(
            "/salary/step3",
            {
                "salary_usd": "1000",
                "exchange_rate": "50",
                "usd_account_id": salary_view_data["usd_account_id"],
                "egp_account_id": salary_view_data["egp_account_id"],
                "date": "2026-03-15",
            },
        )
        assert response.status_code == 200
        assert b"50000" in response.content
        assert b"Savings" in response.content
        assert b'name="alloc_' in response.content


# ---------------------------------------------------------------------------
# POST /salary/confirm — final distribution
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSalaryConfirm:
    def test_success(self, client: Client, salary_view_data: dict[str, Any]) -> None:
        c = set_auth_cookie(client, salary_view_data["session_token"])
        response = c.post(
            "/salary/confirm",
            {
                "salary_usd": "1000",
                "exchange_rate": "50",
                "usd_account_id": salary_view_data["usd_account_id"],
                "egp_account_id": salary_view_data["egp_account_id"],
                "date": "2026-03-15",
            },
        )
        assert response.status_code == 200
        assert b"Salary Distributed" in response.content
        assert b"50000" in response.content

    def test_with_allocation(
        self, client: Client, salary_view_data: dict[str, Any]
    ) -> None:
        c = set_auth_cookie(client, salary_view_data["session_token"])
        alloc_key = f"alloc_{salary_view_data['savings_account_id']}"
        response = c.post(
            "/salary/confirm",
            {
                "salary_usd": "1000",
                "exchange_rate": "50",
                "usd_account_id": salary_view_data["usd_account_id"],
                "egp_account_id": salary_view_data["egp_account_id"],
                "date": "2026-03-15",
                alloc_key: "10000",
            },
        )
        assert response.status_code == 200
        assert b"Salary Distributed" in response.content
        assert b"1 accounts" in response.content

    def test_validation_error_returns_400(
        self, client: Client, salary_view_data: dict[str, Any]
    ) -> None:
        c = set_auth_cookie(client, salary_view_data["session_token"])
        response = c.post(
            "/salary/confirm",
            {
                "salary_usd": "0",
                "exchange_rate": "50",
                "usd_account_id": salary_view_data["usd_account_id"],
                "egp_account_id": salary_view_data["egp_account_id"],
            },
        )
        assert response.status_code == 400
