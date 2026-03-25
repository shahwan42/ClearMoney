"""
Budget view tests — HTTP-level tests for /budgets/* routes.

Tests run against the real database with --reuse-db.
"""

import uuid
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from django.test import Client

from budgets.services import BudgetService
from conftest import SessionFactory, UserFactory, set_auth_cookie
from core.middleware import COOKIE_NAME
from core.models import Session, User
from tests.factories import CategoryFactory


@pytest.fixture
def budget_view_data(db):
    """User + session + two expense categories for budget view tests."""
    user = UserFactory()
    session = SessionFactory(user=user)
    user_id = str(user.id)
    cat1 = CategoryFactory(user_id=user.id, name="Groceries", type="expense")
    cat2 = CategoryFactory(user_id=user.id, name="Transport", type="expense")

    yield {
        "user_id": user_id,
        "session_token": session.token,
        "cat1_id": str(cat1.id),
        "cat2_id": str(cat2.id),
    }


# ---------------------------------------------------------------------------
# Budgets page
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestBudgetsPage:
    def test_200_empty_state(self, client, budget_view_data):
        c = set_auth_cookie(client, budget_view_data["session_token"])
        response = c.get("/budgets")
        assert response.status_code == 200
        assert b"Budgets" in response.content
        assert b"No budgets set" in response.content

    def test_200_with_budgets(self, client, budget_view_data):
        c = set_auth_cookie(client, budget_view_data["session_token"])
        # Create a budget
        c.post(
            "/budgets/add",
            {
                "category_id": budget_view_data["cat1_id"],
                "monthly_limit": "5000",
                "currency": "EGP",
            },
        )
        response = c.get("/budgets")
        assert response.status_code == 200
        assert b"Groceries" in response.content
        assert b"5,000" in response.content

    def test_shows_category_dropdown(self, client, budget_view_data):
        c = set_auth_cookie(client, budget_view_data["session_token"])
        response = c.get("/budgets")
        assert response.status_code == 200
        assert b"Groceries" in response.content
        assert b"Transport" in response.content

    def test_unauthenticated_redirects(self, client):
        response = client.get("/budgets")
        assert response.status_code == 302
        assert "/login" in response.url


# ---------------------------------------------------------------------------
# Create budget
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestBudgetAdd:
    def test_creates_budget_and_redirects(self, client, budget_view_data):
        c = set_auth_cookie(client, budget_view_data["session_token"])
        response = c.post(
            "/budgets/add",
            {
                "category_id": budget_view_data["cat1_id"],
                "monthly_limit": "3000",
                "currency": "EGP",
            },
        )
        assert response.status_code == 302
        assert response.url == "/budgets"  # type: ignore[attr-defined]

        # Verify budget appears on page
        page = c.get("/budgets")
        assert b"Groceries" in page.content
        assert b"3,000" in page.content

    def test_missing_category_returns_400(self, client, budget_view_data):
        c = set_auth_cookie(client, budget_view_data["session_token"])
        response = c.post(
            "/budgets/add",
            {"category_id": "", "monthly_limit": "1000", "currency": "EGP"},
        )
        assert response.status_code == 400

    def test_invalid_limit_returns_400(self, client, budget_view_data):
        c = set_auth_cookie(client, budget_view_data["session_token"])
        response = c.post(
            "/budgets/add",
            {
                "category_id": budget_view_data["cat1_id"],
                "monthly_limit": "abc",
                "currency": "EGP",
            },
        )
        assert response.status_code == 400

    def test_zero_limit_returns_400(self, client, budget_view_data):
        c = set_auth_cookie(client, budget_view_data["session_token"])
        response = c.post(
            "/budgets/add",
            {
                "category_id": budget_view_data["cat1_id"],
                "monthly_limit": "0",
                "currency": "EGP",
            },
        )
        assert response.status_code == 400

    def test_duplicate_returns_400(self, client, budget_view_data):
        c = set_auth_cookie(client, budget_view_data["session_token"])
        c.post(
            "/budgets/add",
            {
                "category_id": budget_view_data["cat1_id"],
                "monthly_limit": "1000",
                "currency": "EGP",
            },
        )
        response = c.post(
            "/budgets/add",
            {
                "category_id": budget_view_data["cat1_id"],
                "monthly_limit": "2000",
                "currency": "EGP",
            },
        )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Delete budget
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestBudgetDelete:
    def test_deletes_and_redirects(self, client, budget_view_data):
        c = set_auth_cookie(client, budget_view_data["session_token"])
        # Create first
        c.post(
            "/budgets/add",
            {
                "category_id": budget_view_data["cat1_id"],
                "monthly_limit": "1000",
                "currency": "EGP",
            },
        )
        # Get the budget ID from the page
        page = c.get("/budgets")
        content = page.content.decode()
        # Find the delete form action URL which contains the UUID
        import re

        match = re.search(r"/budgets/([0-9a-f-]+)/delete", content)
        assert match is not None, "Delete form not found on page"
        budget_id = match.group(1)

        # Delete it
        response = c.post(f"/budgets/{budget_id}/delete")
        assert response.status_code == 302
        assert response.url == "/budgets"  # type: ignore[attr-defined]

        # Verify empty state
        page = c.get("/budgets")
        assert b"No budgets set" in page.content

    def test_delete_nonexistent_redirects(self, client, budget_view_data):
        c = set_auth_cookie(client, budget_view_data["session_token"])
        fake_id = str(uuid.uuid4())
        response = c.post(f"/budgets/{fake_id}/delete")
        assert response.status_code == 302

    def test_cannot_delete_other_users_budget(self, client, budget_view_data):
        c = set_auth_cookie(client, budget_view_data["session_token"])
        # Create a budget
        c.post(
            "/budgets/add",
            {
                "category_id": budget_view_data["cat1_id"],
                "monthly_limit": "1000",
                "currency": "EGP",
            },
        )
        # Get budget ID
        page = c.get("/budgets")
        content = page.content.decode()
        import re

        match = re.search(r"/budgets/([0-9a-f-]+)/delete", content)
        assert match is not None
        budget_id = match.group(1)

        # Create another user and try to delete
        user2 = UserFactory()
        session2 = SessionFactory(user=user2)
        c2 = Client()
        c2.cookies[COOKIE_NAME] = session2.token
        c2.post(f"/budgets/{budget_id}/delete")

        # Original user's budget should still exist
        page = c.get("/budgets")
        assert b"Groceries" in page.content

        # Cleanup user2
        Session.objects.filter(user=user2).delete()
        User.objects.filter(id=user2.id).delete()


# ---------------------------------------------------------------------------
# Total budget views
# ---------------------------------------------------------------------------

TZ = ZoneInfo("Africa/Cairo")


@pytest.mark.django_db
class TestTotalBudgetViews:
    """Total budget CRUD via HTTP."""

    def test_budgets_page_shows_total(
        self, client: Client, budget_view_data: dict
    ) -> None:
        c = set_auth_cookie(client, budget_view_data["session_token"])
        svc = BudgetService(budget_view_data["user_id"], TZ)
        svc.set_total_budget(Decimal("15000"), "EGP")
        resp = c.get("/budgets")
        content = resp.content.decode()
        assert "Total Monthly Budget" in content
        assert "15,000" in content

    def test_budgets_page_without_total(
        self, client: Client, budget_view_data: dict
    ) -> None:
        c = set_auth_cookie(client, budget_view_data["session_token"])
        resp = c.get("/budgets")
        assert resp.status_code == 200
        # Should show set-total form prompt
        assert b"Set Total Budget" in resp.content

    def test_set_total_budget(self, client: Client, budget_view_data: dict) -> None:
        c = set_auth_cookie(client, budget_view_data["session_token"])
        resp = c.post(
            "/budgets/total/set",
            {
                "monthly_limit": "15000",
                "currency": "EGP",
            },
        )
        assert resp.status_code == 302
        # Verify it appears on page
        page = c.get("/budgets")
        assert b"15,000" in page.content

    def test_delete_total_budget(self, client: Client, budget_view_data: dict) -> None:
        c = set_auth_cookie(client, budget_view_data["session_token"])
        # Set via HTTP
        c.post("/budgets/total/set", {"monthly_limit": "10000", "currency": "EGP"})
        page = c.get("/budgets")
        assert b"Total Monthly Budget" in page.content
        # Delete via HTTP
        resp = c.post("/budgets/total/delete", {"currency": "EGP"})
        assert resp.status_code == 302
        page = c.get("/budgets")
        assert b"Total Monthly Budget" not in page.content

    def test_set_invalid_limit_rejected(
        self, client: Client, budget_view_data: dict
    ) -> None:
        c = set_auth_cookie(client, budget_view_data["session_token"])
        resp = c.post(
            "/budgets/total/set",
            {
                "monthly_limit": "-1000",
                "currency": "EGP",
            },
        )
        assert resp.status_code == 400

    def test_total_budget_has_aria_progressbar(
        self, client: Client, budget_view_data: dict
    ) -> None:
        c = set_auth_cookie(client, budget_view_data["session_token"])
        svc = BudgetService(budget_view_data["user_id"], TZ)
        svc.set_total_budget(Decimal("15000"), "EGP")
        resp = c.get("/budgets")
        content = resp.content.decode()
        assert 'role="progressbar"' in content
