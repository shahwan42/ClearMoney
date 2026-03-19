"""
Virtual account view tests — HTTP-level tests for /virtual-accounts/* routes.

Port of Go's handler/pages_test.go virtual account tests + expanded coverage.
Tests run against the real database with --reuse-db (Go owns schema).
"""

import re
import uuid

import pytest
from django.db import connection
from django.test import Client

from conftest import SessionFactory, UserFactory
from core.middleware import COOKIE_NAME
from core.models import Session, User
from tests.factories import AccountFactory, InstitutionFactory


@pytest.fixture
def va_view_data(db):
    """User + session + institution + bank account for VA view tests."""
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

    yield {
        "user_id": user_id,
        "session_token": session.token,
        "account_id": str(acct.id),
    }

    # Cleanup
    with connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM virtual_account_allocations WHERE virtual_account_id IN "
            "(SELECT id FROM virtual_accounts WHERE user_id = %s)",
            [user_id],
        )
        cursor.execute("DELETE FROM virtual_accounts WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM accounts WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM institutions WHERE user_id = %s", [user_id])
    Session.objects.filter(user=user).delete()
    User.objects.filter(id=user.id).delete()


def _auth_client(client: Client, token: str) -> Client:
    client.cookies[COOKIE_NAME] = token
    return client


# ---------------------------------------------------------------------------
# List page
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestVirtualAccountsPage:
    def test_200_empty_state(self, client, va_view_data):
        c = _auth_client(client, va_view_data["session_token"])
        response = c.get("/virtual-accounts")
        assert response.status_code == 200
        assert b"Virtual Accounts" in response.content
        assert b"No virtual accounts yet" in response.content

    def test_200_with_vas(self, client, va_view_data):
        c = _auth_client(client, va_view_data["session_token"])
        c.post(
            "/virtual-accounts/add",
            {
                "name": "Emergency Fund",
                "target_amount": "100000",
                "account_id": va_view_data["account_id"],
                "color": "#0d9488",
            },
        )
        response = c.get("/virtual-accounts")
        assert response.status_code == 200
        assert b"Emergency Fund" in response.content

    def test_shows_bank_account_dropdown(self, client, va_view_data):
        c = _auth_client(client, va_view_data["session_token"])
        response = c.get("/virtual-accounts")
        assert response.status_code == 200
        assert b"Checking (EGP)" in response.content

    def test_unauthenticated_redirects(self, client):
        response = client.get("/virtual-accounts")
        assert response.status_code == 302
        assert "/login" in response.url

    def test_shows_over_allocation_warning(self, client, va_view_data):
        c = _auth_client(client, va_view_data["session_token"])
        # Create a VA with balance exceeding account balance
        c.post(
            "/virtual-accounts/add",
            {
                "name": "Big Fund",
                "account_id": va_view_data["account_id"],
            },
        )
        # Get the VA ID from the page
        page = c.get("/virtual-accounts")
        content = page.content.decode()
        match = re.search(r'/virtual-accounts/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"', content)
        assert match is not None
        va_id = match.group(1)

        # Allocate more than account balance
        c.post(f"/virtual-accounts/{va_id}/allocate", {
            "type": "contribution",
            "amount": "60000",
        })

        response = c.get("/virtual-accounts")
        assert response.status_code == 200
        assert b"exceed" in response.content.lower()


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestVirtualAccountAdd:
    def test_creates_and_redirects(self, client, va_view_data):
        c = _auth_client(client, va_view_data["session_token"])
        response = c.post(
            "/virtual-accounts/add",
            {
                "name": "Vacation Fund",
                "target_amount": "50000",
                "account_id": va_view_data["account_id"],
                "color": "#0d9488",
                "icon": "🏖️",
            },
        )
        assert response.status_code == 302
        assert response.url == "/virtual-accounts"  # type: ignore[attr-defined]

        # Verify it appears on the page
        page = c.get("/virtual-accounts")
        assert b"Vacation Fund" in page.content

    def test_missing_name_returns_400(self, client, va_view_data):
        c = _auth_client(client, va_view_data["session_token"])
        response = c.post(
            "/virtual-accounts/add",
            {"name": "", "account_id": va_view_data["account_id"]},
        )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Detail page
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestVirtualAccountDetail:
    def _create_va(self, client: Client, va_view_data: dict) -> str:
        """Create a VA and return its UUID."""
        client.post(
            "/virtual-accounts/add",
            {
                "name": "Test VA",
                "target_amount": "100000",
                "account_id": va_view_data["account_id"],
            },
        )
        page = client.get("/virtual-accounts")
        match = re.search(r'/virtual-accounts/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"', page.content.decode())
        assert match is not None
        return match.group(1)

    def test_200_with_info(self, client, va_view_data):
        c = _auth_client(client, va_view_data["session_token"])
        va_id = self._create_va(c, va_view_data)

        response = c.get(f"/virtual-accounts/{va_id}")
        assert response.status_code == 200
        assert b"Test VA" in response.content
        assert b"Allocate Funds" in response.content
        assert b"History" in response.content

    def test_404_nonexistent(self, client, va_view_data):
        c = _auth_client(client, va_view_data["session_token"])
        fake_id = str(uuid.uuid4())
        response = c.get(f"/virtual-accounts/{fake_id}")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Archive
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestVirtualAccountArchive:
    def test_archives_and_redirects(self, client, va_view_data):
        c = _auth_client(client, va_view_data["session_token"])
        c.post(
            "/virtual-accounts/add",
            {"name": "To Archive", "account_id": va_view_data["account_id"]},
        )
        page = c.get("/virtual-accounts")
        match = re.search(r'/virtual-accounts/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/archive', page.content.decode())
        assert match is not None
        va_id = match.group(1)

        response = c.post(f"/virtual-accounts/{va_id}/archive")
        assert response.status_code == 302

        # Should show empty state
        page = c.get("/virtual-accounts")
        assert b"No virtual accounts yet" in page.content


# ---------------------------------------------------------------------------
# Allocate
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestVirtualAccountAllocate:
    def _create_va(self, client: Client, va_view_data: dict) -> str:
        client.post(
            "/virtual-accounts/add",
            {"name": "Fund", "account_id": va_view_data["account_id"]},
        )
        page = client.get("/virtual-accounts")
        match = re.search(r'/virtual-accounts/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"', page.content.decode())
        assert match is not None
        return match.group(1)

    def test_contribution_works(self, client, va_view_data):
        c = _auth_client(client, va_view_data["session_token"])
        va_id = self._create_va(c, va_view_data)

        response = c.post(
            f"/virtual-accounts/{va_id}/allocate",
            {"type": "contribution", "amount": "5000", "note": "Salary"},
        )
        assert response.status_code == 302

        page = c.get(f"/virtual-accounts/{va_id}")
        assert b"5,000" in page.content
        assert b"Salary" in page.content

    def test_withdrawal_works(self, client, va_view_data):
        c = _auth_client(client, va_view_data["session_token"])
        va_id = self._create_va(c, va_view_data)

        # First add some money
        c.post(
            f"/virtual-accounts/{va_id}/allocate",
            {"type": "contribution", "amount": "5000"},
        )
        # Then withdraw
        c.post(
            f"/virtual-accounts/{va_id}/allocate",
            {"type": "withdrawal", "amount": "2000"},
        )

        page = c.get(f"/virtual-accounts/{va_id}")
        assert b"3,000" in page.content

    def test_invalid_amount_returns_400(self, client, va_view_data):
        c = _auth_client(client, va_view_data["session_token"])
        va_id = self._create_va(c, va_view_data)

        response = c.post(
            f"/virtual-accounts/{va_id}/allocate",
            {"type": "contribution", "amount": "abc"},
        )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Toggle exclude
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestVirtualAccountToggleExclude:
    def test_toggles_and_redirects(self, client, va_view_data):
        c = _auth_client(client, va_view_data["session_token"])
        c.post(
            "/virtual-accounts/add",
            {"name": "Toggle Test", "account_id": va_view_data["account_id"]},
        )
        page = c.get("/virtual-accounts")
        match = re.search(r'/virtual-accounts/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"', page.content.decode())
        assert match is not None
        va_id = match.group(1)

        # Toggle on
        response = c.post(f"/virtual-accounts/{va_id}/toggle-exclude")
        assert response.status_code == 302

        # Verify the badge appears
        page = c.get(f"/virtual-accounts/{va_id}")
        assert b"Excluded from net worth" in page.content


# ---------------------------------------------------------------------------
# Edit form (HTMX partial)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestVirtualAccountEditForm:
    def test_returns_partial_html(self, client, va_view_data):
        c = _auth_client(client, va_view_data["session_token"])
        c.post(
            "/virtual-accounts/add",
            {"name": "Edit Me", "account_id": va_view_data["account_id"]},
        )
        page = c.get("/virtual-accounts")
        match = re.search(r'/virtual-accounts/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"', page.content.decode())
        assert match is not None
        va_id = match.group(1)

        response = c.get(f"/virtual-accounts/{va_id}/edit-form")
        assert response.status_code == 200
        assert b"Edit Virtual Account" in response.content
        assert b'name="name"' in response.content

    def test_404_nonexistent(self, client, va_view_data):
        c = _auth_client(client, va_view_data["session_token"])
        fake_id = str(uuid.uuid4())
        response = c.get(f"/virtual-accounts/{fake_id}/edit-form")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Update (HTMX form submission)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestVirtualAccountUpdate:
    def test_updates_and_redirects(self, client, va_view_data):
        c = _auth_client(client, va_view_data["session_token"])
        c.post(
            "/virtual-accounts/add",
            {"name": "Old Name", "account_id": va_view_data["account_id"]},
        )
        page = c.get("/virtual-accounts")
        match = re.search(r'/virtual-accounts/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"', page.content.decode())
        assert match is not None
        va_id = match.group(1)

        response = c.post(
            f"/virtual-accounts/{va_id}/edit",
            {
                "name": "New Name",
                "color": "#ff0000",
                "account_id": va_view_data["account_id"],
            },
        )
        assert response.status_code == 302

        # Verify update took effect
        page = c.get(f"/virtual-accounts/{va_id}")
        assert b"New Name" in page.content

    def test_validation_error_returns_422(self, client, va_view_data):
        c = _auth_client(client, va_view_data["session_token"])
        c.post(
            "/virtual-accounts/add",
            {"name": "Test", "account_id": va_view_data["account_id"]},
        )
        page = c.get("/virtual-accounts")
        match = re.search(r'/virtual-accounts/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"', page.content.decode())
        assert match is not None
        va_id = match.group(1)

        response = c.post(
            f"/virtual-accounts/{va_id}/edit",
            {"name": "", "account_id": va_view_data["account_id"]},
        )
        assert response.status_code == 422
        assert b"name is required" in response.content


# ---------------------------------------------------------------------------
# Legacy redirects
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestLegacyRedirects:
    def test_virtual_funds_redirects(self, client, va_view_data):
        c = _auth_client(client, va_view_data["session_token"])
        response = c.get("/virtual-funds")
        assert response.status_code == 301
        assert "/virtual-accounts" in response.url  # type: ignore[attr-defined]

    def test_virtual_fund_detail_redirects(self, client, va_view_data):
        c = _auth_client(client, va_view_data["session_token"])
        fake_id = str(uuid.uuid4())
        response = c.get(f"/virtual-funds/{fake_id}")
        assert response.status_code == 301
        assert f"/virtual-accounts/{fake_id}" in response.url  # type: ignore[attr-defined]
