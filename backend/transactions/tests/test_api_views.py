"""
Transaction API view tests — HTTP-level tests for /api/transactions/* JSON API.

Port of Go's handler/transaction_test.go.
"""

import json
import uuid

import pytest
from django.db import connection
from django.test import Client

from conftest import SessionFactory, UserFactory
from core.middleware import COOKIE_NAME
from core.models import Session, User


@pytest.fixture
def tx_api_data(db):
    """User + session + institution + EGP account (10000) + USD account (500) + category."""
    user = UserFactory()
    session = SessionFactory(user=user)
    user_id = str(user.id)
    inst_id = str(uuid.uuid4())
    egp_id = str(uuid.uuid4())
    usd_id = str(uuid.uuid4())
    cat_id = str(uuid.uuid4())

    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO institutions (id, user_id, name, type) VALUES (%s, %s, %s, 'bank')",
            [inst_id, user_id, "Test Bank"],
        )
        cursor.execute(
            "INSERT INTO accounts (id, user_id, institution_id, name, type, currency,"
            " current_balance, initial_balance)"
            " VALUES (%s, %s, %s, %s, 'savings'::account_type, 'EGP'::currency_type, %s, %s)",
            [egp_id, user_id, inst_id, "EGP Savings", 10000, 10000],
        )
        cursor.execute(
            "INSERT INTO accounts (id, user_id, institution_id, name, type, currency,"
            " current_balance, initial_balance)"
            " VALUES (%s, %s, %s, %s, 'savings'::account_type, 'USD'::currency_type, %s, %s)",
            [usd_id, user_id, inst_id, "USD Savings", 500, 500],
        )
        cursor.execute(
            "INSERT INTO categories (id, user_id, name, type, is_system, display_order) "
            "VALUES (%s, %s, 'Groceries', 'expense', true, 1)",
            [cat_id, user_id],
        )

    yield {
        "user_id": user_id,
        "session_token": session.token,
        "inst_id": inst_id,
        "egp_id": egp_id,
        "usd_id": usd_id,
        "cat_id": cat_id,
    }

    # Cleanup
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM transactions WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM categories WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM accounts WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM institutions WHERE user_id = %s", [user_id])
    Session.objects.filter(user=user).delete()
    User.objects.filter(id=user.id).delete()


def _auth_client(client: Client, token: str) -> Client:
    client.cookies[COOKIE_NAME] = token
    return client


@pytest.mark.django_db
class TestTransactionAPI:
    def test_list_empty(self, client, tx_api_data):
        c = _auth_client(client, tx_api_data["session_token"])
        resp = c.get("/api/transactions")
        assert resp.status_code == 200
        assert json.loads(resp.content) == []

    def test_create_returns_tx_and_balance(self, client, tx_api_data):
        c = _auth_client(client, tx_api_data["session_token"])
        resp = c.post(
            "/api/transactions",
            data=json.dumps({
                "type": "expense",
                "amount": 250,
                "account_id": tx_api_data["egp_id"],
                "category_id": tx_api_data["cat_id"],
                "date": "2026-03-19",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 201
        body = json.loads(resp.content)
        assert "transaction" in body
        assert "new_balance" in body
        tx = body["transaction"]
        assert tx["type"] == "expense"
        assert tx["amount"] == 250
        assert body["new_balance"] == 9750  # 10000 - 250

    def test_get_by_id(self, client, tx_api_data):
        c = _auth_client(client, tx_api_data["session_token"])
        # Create first
        resp = c.post(
            "/api/transactions",
            data=json.dumps({
                "type": "expense",
                "amount": 100,
                "account_id": tx_api_data["egp_id"],
                "category_id": tx_api_data["cat_id"],
                "date": "2026-03-19",
            }),
            content_type="application/json",
        )
        tx_id = json.loads(resp.content)["transaction"]["id"]

        resp = c.get(f"/api/transactions/{tx_id}")
        assert resp.status_code == 200
        assert json.loads(resp.content)["id"] == tx_id

    def test_delete(self, client, tx_api_data):
        c = _auth_client(client, tx_api_data["session_token"])
        # Create
        resp = c.post(
            "/api/transactions",
            data=json.dumps({
                "type": "expense",
                "amount": 50,
                "account_id": tx_api_data["egp_id"],
                "category_id": tx_api_data["cat_id"],
                "date": "2026-03-19",
            }),
            content_type="application/json",
        )
        tx_id = json.loads(resp.content)["transaction"]["id"]

        # Delete
        resp = c.delete(f"/api/transactions/{tx_id}")
        assert resp.status_code == 204

        # Verify gone
        resp = c.get(f"/api/transactions/{tx_id}")
        assert resp.status_code == 404

    def test_list_with_account_filter(self, client, tx_api_data):
        c = _auth_client(client, tx_api_data["session_token"])
        # Create a transaction on EGP account
        c.post(
            "/api/transactions",
            data=json.dumps({
                "type": "expense",
                "amount": 75,
                "account_id": tx_api_data["egp_id"],
                "category_id": tx_api_data["cat_id"],
                "date": "2026-03-19",
            }),
            content_type="application/json",
        )

        # Filter by EGP account
        resp = c.get(f"/api/transactions?account_id={tx_api_data['egp_id']}")
        assert resp.status_code == 200
        txs = json.loads(resp.content)
        assert len(txs) >= 1

        # Filter by USD account (should be empty — no USD transactions yet)
        resp = c.get(f"/api/transactions?account_id={tx_api_data['usd_id']}")
        assert resp.status_code == 200
        assert json.loads(resp.content) == []

    def test_list_with_limit(self, client, tx_api_data):
        c = _auth_client(client, tx_api_data["session_token"])
        # Create 3 transactions
        for i in range(3):
            c.post(
                "/api/transactions",
                data=json.dumps({
                    "type": "expense",
                    "amount": 10 + i,
                    "account_id": tx_api_data["egp_id"],
                    "category_id": tx_api_data["cat_id"],
                    "date": "2026-03-19",
                }),
                content_type="application/json",
            )

        resp = c.get("/api/transactions?limit=2")
        assert resp.status_code == 200
        txs = json.loads(resp.content)
        assert len(txs) == 2

    def test_transfer(self, client, tx_api_data):
        c = _auth_client(client, tx_api_data["session_token"])

        # Create a second EGP account for same-currency transfer
        egp2_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO accounts (id, user_id, institution_id, name, type, currency,"
                " current_balance, initial_balance)"
                " VALUES (%s, %s, %s, %s, 'savings'::account_type, 'EGP'::currency_type, %s, %s)",
                [egp2_id, tx_api_data["user_id"], tx_api_data["inst_id"],
                 "EGP Savings 2", 5000, 5000],
            )

        resp = c.post(
            "/api/transactions/transfer",
            data=json.dumps({
                "source_account_id": tx_api_data["egp_id"],
                "dest_account_id": egp2_id,
                "amount": 1000,
                "date": "2026-03-19",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 201
        body = json.loads(resp.content)
        assert "debit" in body
        assert "credit" in body
        assert body["debit"]["balance_delta"] == -1000
        assert body["credit"]["balance_delta"] == 1000

    def test_exchange(self, client, tx_api_data):
        c = _auth_client(client, tx_api_data["session_token"])
        resp = c.post(
            "/api/transactions/exchange",
            data=json.dumps({
                "source_account_id": tx_api_data["usd_id"],
                "dest_account_id": tx_api_data["egp_id"],
                "amount": 100,
                "rate": 50.5,
                "date": "2026-03-19",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 201
        body = json.loads(resp.content)
        assert "debit" in body
        assert "credit" in body

    def test_create_invalid_json(self, client, tx_api_data):
        c = _auth_client(client, tx_api_data["session_token"])
        resp = c.post(
            "/api/transactions",
            data="not json",
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_unauthenticated(self, client):
        resp = client.get("/api/transactions")
        assert resp.status_code == 302
