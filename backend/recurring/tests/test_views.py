"""
Recurring rules view tests — HTTP-level tests for /recurring* routes.

Tests run against the real database with --reuse-db.
"""

import uuid
from datetime import date, timedelta

import pytest
from django.test import Client

from conftest import SessionFactory, UserFactory, set_auth_cookie
from recurring.models import RecurringRule
from tests.factories import AccountFactory, CategoryFactory, InstitutionFactory
from transactions.models import Transaction


@pytest.fixture
def rec_view_data(db):
    """User + session + institution + account + category for recurring view tests."""
    user = UserFactory()
    session = SessionFactory(user=user)
    user_id = str(user.id)

    inst = InstitutionFactory(user_id=user.id)
    acct = AccountFactory(
        user_id=user.id,
        institution_id=inst.id,
        name="Checking",
        currency="EGP",
        current_balance=50000,
        initial_balance=50000,
    )
    cat = CategoryFactory(user_id=user.id, name="Bills", type="expense")

    yield {
        "user_id": user_id,
        "session_token": session.token,
        "account_id": str(acct.id),
        "category_id": str(cat.id),
    }


def _create_rule(client: Client, data: dict) -> None:
    """Helper: POST /recurring/add to create a rule."""
    client.post("/recurring/add", data)


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRecurringPage:
    def test_200_empty_state(self, client, rec_view_data):
        c = set_auth_cookie(client, rec_view_data["session_token"])
        response = c.get("/recurring")
        assert response.status_code == 200
        assert b"Recurring Transactions" in response.content
        assert b"No recurring rules yet" in response.content

    def test_200_with_rules(self, client, rec_view_data):
        c = set_auth_cookie(client, rec_view_data["session_token"])
        _create_rule(
            c,
            {
                "type": "expense",
                "amount": "100",
                "account_id": rec_view_data["account_id"],
                "category_id": rec_view_data["category_id"],
                "note": "Netflix",
                "frequency": "monthly",
                "next_due_date": "2026-04-01",
            },
        )
        response = c.get("/recurring")
        assert response.status_code == 200
        assert b"Netflix" in response.content

    def test_shows_pending_rules(self, client, rec_view_data):
        """Due rules with auto_confirm=false appear in pending section."""
        c = set_auth_cookie(client, rec_view_data["session_token"])
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        _create_rule(
            c,
            {
                "type": "expense",
                "amount": "200",
                "account_id": rec_view_data["account_id"],
                "note": "Pending Rule",
                "frequency": "monthly",
                "next_due_date": yesterday,
                # no auto_confirm → defaults to false
            },
        )
        response = c.get("/recurring")
        assert response.status_code == 200
        assert b"Pending Confirmation" in response.content
        assert b"Pending Rule" in response.content

    def test_archived_category_excluded_from_form(self, client, rec_view_data):
        """Archived categories must not appear in the recurring rule form dropdown."""  # gap: functional
        CategoryFactory(
            user_id=rec_view_data["user_id"],
            name="Archived Cat",
            type="expense",
            is_archived=True,
        )
        c = set_auth_cookie(client, rec_view_data["session_token"])
        response = c.get("/recurring")
        assert response.status_code == 200
        assert b"Archived Cat" not in response.content

    def test_unauthenticated_redirects(self, client):
        response = client.get("/recurring")
        assert response.status_code == 302


# ---------------------------------------------------------------------------
# Add
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRecurringAdd:
    def test_creates_rule(self, client, rec_view_data):
        c = set_auth_cookie(client, rec_view_data["session_token"])
        response = c.post(
            "/recurring/add",
            {
                "type": "expense",
                "amount": "150",
                "account_id": rec_view_data["account_id"],
                "category_id": rec_view_data["category_id"],
                "note": "Insurance",
                "frequency": "monthly",
                "next_due_date": "2026-04-15",
                "auto_confirm": "true",
            },
        )
        assert response.status_code == 200
        # Rule list partial returned with the new rule
        assert b"Insurance" in response.content

    def test_missing_amount_400(self, client, rec_view_data):
        c = set_auth_cookie(client, rec_view_data["session_token"])
        response = c.post(
            "/recurring/add",
            {
                "type": "expense",
                "amount": "",
                "account_id": rec_view_data["account_id"],
                "frequency": "monthly",
                "next_due_date": "2026-04-01",
            },
        )
        assert response.status_code == 400

    def test_currency_from_account(self, client, rec_view_data):
        """Currency should come from account, not form."""
        c = set_auth_cookie(client, rec_view_data["session_token"])
        _create_rule(
            c,
            {
                "type": "expense",
                "amount": "100",
                "account_id": rec_view_data["account_id"],
                "frequency": "monthly",
                "next_due_date": "2026-04-01",
            },
        )

        # Verify currency is EGP (taken from the account, not a form field)
        rule = RecurringRule.objects.filter(user_id=rec_view_data["user_id"]).first()
        assert rule is not None
        assert rule.template_transaction["currency"] == "EGP"

    def test_currency_fallback_for_unknown_account(self, client, rec_view_data):
        """Unknown account_id falls back to EGP for currency."""  # gap: functional
        c = set_auth_cookie(client, rec_view_data["session_token"])
        _create_rule(
            c,
            {
                "type": "expense",
                "amount": "100",
                "account_id": str(uuid.uuid4()),  # nonexistent account
                "frequency": "monthly",
                "next_due_date": "2026-04-01",
            },
        )
        rule = (
            RecurringRule.objects.filter(user_id=rec_view_data["user_id"])
            .order_by("-created_at")
            .first()
        )
        assert rule is not None
        assert rule.template_transaction["currency"] == "EGP"


# ---------------------------------------------------------------------------
# Confirm
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRecurringConfirm:
    def test_creates_transaction(self, client, rec_view_data):
        c = set_auth_cookie(client, rec_view_data["session_token"])
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        _create_rule(
            c,
            {
                "type": "expense",
                "amount": "300",
                "account_id": rec_view_data["account_id"],
                "note": "Confirm Me",
                "frequency": "monthly",
                "next_due_date": yesterday,
            },
        )

        # Get the rule ID via ORM
        rule = RecurringRule.objects.filter(user_id=rec_view_data["user_id"]).first()
        assert rule is not None
        rule_id = str(rule.id)

        response = c.post(f"/recurring/{rule_id}/confirm")
        assert response.status_code == 200

        # Transaction should exist
        assert Transaction.objects.filter(recurring_rule_id=rule.id).count() == 1


# ---------------------------------------------------------------------------
# Skip
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRecurringSkip:
    def test_advances_date(self, client, rec_view_data):
        c = set_auth_cookie(client, rec_view_data["session_token"])
        yesterday = date.today() - timedelta(days=1)
        _create_rule(
            c,
            {
                "type": "expense",
                "amount": "100",
                "account_id": rec_view_data["account_id"],
                "frequency": "weekly",
                "next_due_date": yesterday.isoformat(),
            },
        )

        # Get rule ID via ORM
        rule = RecurringRule.objects.filter(user_id=rec_view_data["user_id"]).first()
        assert rule is not None
        rule_id = str(rule.id)

        response = c.post(f"/recurring/{rule_id}/skip")
        assert response.status_code == 200

        # Date should have advanced by 7 days
        rule.refresh_from_db()
        assert rule.next_due_date == yesterday + timedelta(days=7)

        # No transaction created
        assert Transaction.objects.filter(recurring_rule_id=rule.id).count() == 0


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRecurringDelete:
    def test_removes_rule(self, client, rec_view_data):
        c = set_auth_cookie(client, rec_view_data["session_token"])
        _create_rule(
            c,
            {
                "type": "expense",
                "amount": "100",
                "account_id": rec_view_data["account_id"],
                "frequency": "monthly",
                "next_due_date": "2026-04-01",
            },
        )

        # Get rule ID via ORM
        rule = RecurringRule.objects.filter(user_id=rec_view_data["user_id"]).first()
        assert rule is not None
        rule_id = str(rule.id)

        response = c.delete(f"/recurring/{rule_id}")
        assert response.status_code == 200

        # Rule should be gone
        assert RecurringRule.objects.filter(id=rule_id).count() == 0

    def test_unauthenticated_redirects(self, client):
        import uuid

        response = client.delete(f"/recurring/{uuid.uuid4()}")
        assert response.status_code == 302
