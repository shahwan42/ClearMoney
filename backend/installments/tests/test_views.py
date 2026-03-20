"""
Installment view tests — HTTP-level tests for /installments* endpoints.

Tests page load, add, pay, delete, and auth redirects.
Uses authenticated test client with session cookie.
"""

from typing import Any

import pytest
from django.db import connection
from django.test import Client

from conftest import SessionFactory, UserFactory, set_auth_cookie
from core.models import Session, User
from tests.factories import AccountFactory, InstitutionFactory


@pytest.fixture
def inst_view_data(db: object) -> Any:  # noqa: ARG001
    """User + session + account for view tests. Cleans up on teardown."""
    user = UserFactory()
    session = SessionFactory(user=user)
    user_id = str(user.id)
    inst = InstitutionFactory(user_id=user.id)
    account = AccountFactory(
        user_id=user.id,
        institution_id=inst.id,
        name="Test Credit Card",
        type="credit_card",
        currency="EGP",
        current_balance=0,
    )

    yield {
        "user_id": user_id,
        "session_token": session.token,
        "account_id": str(account.id),
    }

    # Cleanup (FK ordering)
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM transactions WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM installment_plans WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM accounts WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM institutions WHERE user_id = %s", [user_id])
    Session.objects.filter(user_id=user_id).delete()
    User.objects.filter(id=user_id).delete()


def _create_plan(client: Client, token: str, account_id: str) -> None:
    """Helper to create a test installment plan via the add endpoint."""
    c = set_auth_cookie(client, token)
    c.post(
        "/installments/add",
        {
            "description": "iPhone 16 Pro",
            "total_amount": "60000",
            "num_installments": "12",
            "account_id": account_id,
            "start_date": "2026-01-15",
        },
    )


# ---------------------------------------------------------------------------
# GET /installments — page load
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestInstallmentsPage:
    def test_200(self, client: Client, inst_view_data: dict[str, Any]) -> None:
        c = set_auth_cookie(client, inst_view_data["session_token"])
        response = c.get("/installments")
        assert response.status_code == 200
        assert b"Installment Plans" in response.content

    def test_empty_state(self, client: Client, inst_view_data: dict[str, Any]) -> None:
        c = set_auth_cookie(client, inst_view_data["session_token"])
        response = c.get("/installments")
        assert b"No installment plans yet." in response.content

    def test_shows_plan(self, client: Client, inst_view_data: dict[str, Any]) -> None:
        _create_plan(
            client, inst_view_data["session_token"], inst_view_data["account_id"]
        )
        c = set_auth_cookie(client, inst_view_data["session_token"])
        response = c.get("/installments")
        assert b"iPhone 16 Pro" in response.content
        assert b"5,000" in response.content  # monthly amount

    def test_shows_account_dropdown(
        self, client: Client, inst_view_data: dict[str, Any]
    ) -> None:
        c = set_auth_cookie(client, inst_view_data["session_token"])
        response = c.get("/installments")
        assert b"Test Credit Card" in response.content

    def test_unauthenticated_redirects(self, client: Client) -> None:
        response = client.get("/installments")
        assert response.status_code == 302
        assert "/login" in response.url  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# POST /installments/add — create plan
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestInstallmentAdd:
    def test_creates_and_redirects(
        self, client: Client, inst_view_data: dict[str, Any]
    ) -> None:
        c = set_auth_cookie(client, inst_view_data["session_token"])
        response = c.post(
            "/installments/add",
            {
                "description": "MacBook Pro",
                "total_amount": "120000",
                "num_installments": "24",
                "account_id": inst_view_data["account_id"],
                "start_date": "2026-03-01",
            },
        )
        # htmx_redirect returns 200 with HX-Redirect or 302 for standard POST
        assert response.status_code in (200, 302)

        # Verify plan was created
        c2 = set_auth_cookie(client, inst_view_data["session_token"])
        page = c2.get("/installments")
        assert b"MacBook Pro" in page.content

    def test_missing_description_returns_400(
        self, client: Client, inst_view_data: dict[str, Any]
    ) -> None:
        c = set_auth_cookie(client, inst_view_data["session_token"])
        response = c.post(
            "/installments/add",
            {
                "description": "",
                "total_amount": "60000",
                "num_installments": "12",
                "account_id": inst_view_data["account_id"],
            },
        )
        assert response.status_code == 400

    def test_zero_total_returns_400(
        self, client: Client, inst_view_data: dict[str, Any]
    ) -> None:
        c = set_auth_cookie(client, inst_view_data["session_token"])
        response = c.post(
            "/installments/add",
            {
                "description": "Test",
                "total_amount": "0",
                "num_installments": "12",
                "account_id": inst_view_data["account_id"],
            },
        )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# POST /installments/<id>/pay — record payment
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestInstallmentPay:
    def test_records_payment_and_redirects(
        self, client: Client, inst_view_data: dict[str, Any]
    ) -> None:
        _create_plan(
            client, inst_view_data["session_token"], inst_view_data["account_id"]
        )

        # Get the plan ID
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM installment_plans WHERE user_id = %s LIMIT 1",
                [inst_view_data["user_id"]],
            )
            plan_id = cursor.fetchone()[0]

        c = set_auth_cookie(client, inst_view_data["session_token"])
        response = c.post(f"/installments/{plan_id}/pay")
        assert response.status_code in (200, 302)

        # Verify remaining decremented
        c2 = set_auth_cookie(client, inst_view_data["session_token"])
        page = c2.get("/installments")
        assert b"1/12 paid" in page.content

    def test_fully_paid_returns_400(
        self, client: Client, inst_view_data: dict[str, Any]
    ) -> None:
        # Create a 1-installment plan
        c = set_auth_cookie(client, inst_view_data["session_token"])
        c.post(
            "/installments/add",
            {
                "description": "Quick Plan",
                "total_amount": "1000",
                "num_installments": "1",
                "account_id": inst_view_data["account_id"],
                "start_date": "2026-01-15",
            },
        )

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM installment_plans WHERE user_id = %s LIMIT 1",
                [inst_view_data["user_id"]],
            )
            plan_id = cursor.fetchone()[0]

        # Pay once (completes the plan)
        c2 = set_auth_cookie(client, inst_view_data["session_token"])
        c2.post(f"/installments/{plan_id}/pay")

        # Second pay should fail
        c3 = set_auth_cookie(client, inst_view_data["session_token"])
        response = c3.post(f"/installments/{plan_id}/pay")
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /installments/<id> — delete plan
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestInstallmentDelete:
    def test_deletes_plan(self, client: Client, inst_view_data: dict[str, Any]) -> None:
        _create_plan(
            client, inst_view_data["session_token"], inst_view_data["account_id"]
        )

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM installment_plans WHERE user_id = %s LIMIT 1",
                [inst_view_data["user_id"]],
            )
            plan_id = cursor.fetchone()[0]

        c = set_auth_cookie(client, inst_view_data["session_token"])
        response = c.delete(f"/installments/{plan_id}")
        assert response.status_code in (200, 302)

        # Verify plan was deleted
        c2 = set_auth_cookie(client, inst_view_data["session_token"])
        page = c2.get("/installments")
        assert b"No installment plans yet." in page.content
