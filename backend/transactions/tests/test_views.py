"""
Transaction view tests — HTTP-level tests for all /transactions/*, /transfers/*,
/exchange/*, /batch-entry, and /fawry-cashout routes.

Uses raw SQL fixtures for test data setup.
"""

import json
import uuid
from datetime import date

import pytest
from django.db import connection

from conftest import SessionFactory, UserFactory, set_auth_cookie
from core.models import Session, User


@pytest.fixture
def tx_view_data(db):
    """User + session + institution + EGP savings account + category."""
    user = UserFactory()
    session = SessionFactory(user=user)
    user_id = str(user.id)
    inst_id = str(uuid.uuid4())
    egp_id = str(uuid.uuid4())
    cat_id = str(uuid.uuid4())

    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO institutions (id, user_id, name, type) VALUES (%s, %s, %s, 'bank')",
            [inst_id, user_id, "Test Bank"],
        )
        cursor.execute(
            "INSERT INTO accounts (id, user_id, institution_id, name, type, currency,"
            " current_balance, initial_balance)"
            " VALUES (%s, %s, %s, %s, 'savings', 'EGP', %s, %s)",
            [egp_id, user_id, inst_id, "EGP Savings", 10000, 10000],
        )
        cursor.execute(
            "INSERT INTO categories (id, user_id, name, type)"
            " VALUES (%s, %s, %s, 'expense')",
            [cat_id, user_id, "Food"],
        )

    yield {
        "user_id": user_id,
        "session_token": session.token,
        "egp_id": egp_id,
        "cat_id": cat_id,
    }

    with connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM virtual_account_allocations WHERE transaction_id IN (SELECT id FROM transactions WHERE user_id = %s)",
            [user_id],
        )
        cursor.execute("DELETE FROM transactions WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM accounts WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM categories WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM institutions WHERE user_id = %s", [user_id])
    Session.objects.filter(user=user).delete()
    User.objects.filter(id=user.id).delete()


# ---------------------------------------------------------------------------
# Transaction list page
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTransactionsList:
    def test_200(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/transactions")
        assert response.status_code == 200
        assert b"Transactions" in response.content

    def test_partial_returns_fragment(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/transactions/list", HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        # Partial should not contain full page structure
        assert b"<!DOCTYPE" not in response.content

    def test_unauthenticated_redirects(self, client):
        response = client.get("/transactions")
        assert response.status_code == 302
        assert "/login" in response.url


# ---------------------------------------------------------------------------
# Transaction new page
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTransactionNew:
    def test_200(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/transactions/new")
        assert response.status_code == 200
        assert b"New Transaction" in response.content

    def test_prefill_with_dup(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        # Create a transaction first
        tx_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, note, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 500, 'EGP', %s, 'Test note', -500)",
                [
                    tx_id,
                    tx_view_data["user_id"],
                    tx_view_data["egp_id"],
                    date(2026, 3, 15),
                ],
            )
        response = c.get(f"/transactions/new?dup={tx_id}")
        assert response.status_code == 200
        assert b"Test note" in response.content


# ---------------------------------------------------------------------------
# Transaction CRUD
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTransactionCRUD:
    def test_create_success(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.post(
            "/transactions",
            {
                "type": "expense",
                "amount": "500",
                "account_id": tx_view_data["egp_id"],
                "category_id": tx_view_data["cat_id"],
                "date": "2026-03-15",
            },
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        assert b"Transaction saved!" in response.content

    def test_create_validation_error(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.post(
            "/transactions",
            {
                "type": "expense",
                "amount": "0",
                "account_id": tx_view_data["egp_id"],
            },
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 400

    def test_edit_form(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        tx_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 200, 'EGP', %s, -200)",
                [
                    tx_id,
                    tx_view_data["user_id"],
                    tx_view_data["egp_id"],
                    date(2026, 3, 15),
                ],
            )
        response = c.get(f"/transactions/edit/{tx_id}", HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        assert b"Save" in response.content

    def test_update_via_put(self, client, tx_view_data):
        """PUT /transactions/<id> should update the transaction amount."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        tx_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 200, 'EGP', %s, -200)",
                [
                    tx_id,
                    tx_view_data["user_id"],
                    tx_view_data["egp_id"],
                    date(2026, 3, 15),
                ],
            )
            cursor.execute(
                "UPDATE accounts SET current_balance = current_balance - 200 WHERE id = %s",
                [tx_view_data["egp_id"]],
            )
        response = c.put(
            f"/transactions/{tx_id}",
            data="type=expense&amount=300&category_id=&note=Updated&date=2026-03-15",
            content_type="application/x-www-form-urlencoded",
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.content!r}"
        )

    def test_delete(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        tx_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 200, 'EGP', %s, -200)",
                [
                    tx_id,
                    tx_view_data["user_id"],
                    tx_view_data["egp_id"],
                    date(2026, 3, 15),
                ],
            )
            cursor.execute(
                "UPDATE accounts SET current_balance = current_balance - 200 WHERE id = %s",
                [tx_view_data["egp_id"]],
            )
        response = c.delete(f"/transactions/{tx_id}", HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        assert response.content == b""

    def test_row_partial(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        tx_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 200, 'EGP', %s, -200)",
                [
                    tx_id,
                    tx_view_data["user_id"],
                    tx_view_data["egp_id"],
                    date(2026, 3, 15),
                ],
            )
        response = c.get(f"/transactions/row/{tx_id}", HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        assert b"EGP" in response.content


# ---------------------------------------------------------------------------
# Transfer
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTransferViews:
    def test_transfer_new_page(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/transfers/new")
        assert response.status_code == 200
        assert b"Transfer Between Accounts" in response.content

    def test_transfer_create(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        # Create a second account
        dest_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO accounts (id, user_id, institution_id, name, type, currency,"
                " current_balance, initial_balance)"
                " VALUES (%s, %s, (SELECT id FROM institutions WHERE user_id = %s LIMIT 1),"
                " %s, 'savings', 'EGP', %s, %s)",
                [
                    dest_id,
                    tx_view_data["user_id"],
                    tx_view_data["user_id"],
                    "Dest",
                    5000,
                    5000,
                ],
            )
        response = c.post(
            "/transactions/transfer",
            {
                "source_account_id": tx_view_data["egp_id"],
                "dest_account_id": dest_id,
                "amount": "1000",
                "date": "2026-03-15",
            },
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        assert b"Transfer completed!" in response.content


# ---------------------------------------------------------------------------
# Exchange
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestExchangeViews:
    def test_exchange_new_page(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/exchange/new")
        assert response.status_code == 200
        assert b"Currency Exchange" in response.content


# ---------------------------------------------------------------------------
# Batch entry
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestBatchViews:
    def test_batch_entry_page(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/batch-entry")
        assert response.status_code == 200
        assert b"Batch Entry" in response.content


# ---------------------------------------------------------------------------
# Fawry
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestFawryViews:
    def test_fawry_cashout_page(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/fawry-cashout")
        assert response.status_code == 200
        assert b"Fawry" in response.content


# ---------------------------------------------------------------------------
# Quick entry partials
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestQuickEntryViews:
    def test_quick_entry_form(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/transactions/quick-form", HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        assert b"Quick Entry" in response.content

    def test_quick_transfer_form(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/transactions/quick-transfer", HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        assert b"Quick Transfer" in response.content

    def test_quick_exchange_form(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/exchange/quick-form", HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        assert b"Quick Exchange" in response.content


# ---------------------------------------------------------------------------
# Sync API
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSyncAPI:
    def test_sync_json(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        payload = [
            {"type": "expense", "amount": 100, "account_id": tx_view_data["egp_id"]},
            {"type": "income", "amount": 200, "account_id": tx_view_data["egp_id"]},
        ]
        response = c.post(
            "/sync/transactions",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["created"] == 2
        assert data["failed"] == 0


# ---------------------------------------------------------------------------
# Suggest category
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSuggestCategory:
    def test_returns_text(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/api/transactions/suggest-category?note=test")
        assert response.status_code == 200
