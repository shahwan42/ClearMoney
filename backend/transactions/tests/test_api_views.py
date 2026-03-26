"""
Transaction API view tests — HTTP-level tests for /api/transactions/* JSON API.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from conftest import SessionFactory, UserFactory, set_auth_cookie
from tests.factories import AccountFactory, CategoryFactory, InstitutionFactory

if TYPE_CHECKING:
    from django.test import Client


@pytest.fixture
def tx_api_data(db):
    """User + session + institution + EGP account (10000) + USD account (500) + category."""
    user = UserFactory()
    session = SessionFactory(user=user)
    institution = InstitutionFactory(user_id=user.id, name="Test Bank")
    egp_account = AccountFactory(
        user_id=user.id,
        institution_id=institution.id,
        name="EGP Savings",
        currency="EGP",
        current_balance=10000,
        initial_balance=10000,
    )
    usd_account = AccountFactory(
        user_id=user.id,
        institution_id=institution.id,
        name="USD Savings",
        currency="USD",
        current_balance=500,
        initial_balance=500,
    )
    category = CategoryFactory(
        user_id=user.id,
        name="Groceries",
        type="expense",
        is_system=True,
        display_order=1,
    )
    yield {
        "user_id": str(user.id),
        "session_token": session.token,
        "inst_id": str(institution.id),
        "egp_id": str(egp_account.id),
        "usd_id": str(usd_account.id),
        "cat_id": str(category.id),
    }


@pytest.mark.django_db
class TestTransactionAPI:
    def test_list_empty(self, client, tx_api_data):
        c = set_auth_cookie(client, tx_api_data["session_token"])
        resp = c.get("/api/transactions")
        assert resp.status_code == 200
        body = json.loads(resp.content)
        assert isinstance(body, dict)
        assert body["results"] == []
        assert body["total_count"] == 0
        assert body["has_next"] is False
        assert body["has_previous"] is False

    def test_create_returns_tx_and_balance(self, client, tx_api_data):
        from decimal import Decimal

        c = set_auth_cookie(client, tx_api_data["session_token"])
        resp = c.post(
            "/api/transactions",
            data=json.dumps(
                {
                    "type": "expense",
                    "amount": 250,
                    "account_id": tx_api_data["egp_id"],
                    "category_id": tx_api_data["cat_id"],
                    "date": "2026-03-19",
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 201
        body = json.loads(resp.content)
        assert "transaction" in body
        assert "new_balance" in body
        tx = body["transaction"]
        assert tx["type"] == "expense"
        assert Decimal(tx["amount"]) == Decimal("250")
        assert Decimal(body["new_balance"]) == Decimal("9750")  # 10000 - 250

    def test_get_by_id(self, client, tx_api_data):
        c = set_auth_cookie(client, tx_api_data["session_token"])
        # Create first
        resp = c.post(
            "/api/transactions",
            data=json.dumps(
                {
                    "type": "expense",
                    "amount": 100,
                    "account_id": tx_api_data["egp_id"],
                    "category_id": tx_api_data["cat_id"],
                    "date": "2026-03-19",
                }
            ),
            content_type="application/json",
        )
        tx_id = json.loads(resp.content)["transaction"]["id"]

        resp = c.get(f"/api/transactions/{tx_id}")
        assert resp.status_code == 200
        assert json.loads(resp.content)["id"] == tx_id

    def test_delete(self, client, tx_api_data):
        c = set_auth_cookie(client, tx_api_data["session_token"])
        # Create
        resp = c.post(
            "/api/transactions",
            data=json.dumps(
                {
                    "type": "expense",
                    "amount": 50,
                    "account_id": tx_api_data["egp_id"],
                    "category_id": tx_api_data["cat_id"],
                    "date": "2026-03-19",
                }
            ),
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
        c = set_auth_cookie(client, tx_api_data["session_token"])
        # Create a transaction on EGP account
        c.post(
            "/api/transactions",
            data=json.dumps(
                {
                    "type": "expense",
                    "amount": 75,
                    "account_id": tx_api_data["egp_id"],
                    "category_id": tx_api_data["cat_id"],
                    "date": "2026-03-19",
                }
            ),
            content_type="application/json",
        )

        # Filter by EGP account
        resp = c.get(f"/api/transactions?account_id={tx_api_data['egp_id']}")
        assert resp.status_code == 200
        body = json.loads(resp.content)
        assert isinstance(body, dict)
        assert len(body["results"]) >= 1

        # Filter by USD account (should be empty — no USD transactions yet)
        resp = c.get(f"/api/transactions?account_id={tx_api_data['usd_id']}")
        assert resp.status_code == 200
        body = json.loads(resp.content)
        assert body["results"] == []

    def test_list_with_limit(self, client, tx_api_data):
        c = set_auth_cookie(client, tx_api_data["session_token"])
        # Create 3 transactions
        for i in range(3):
            c.post(
                "/api/transactions",
                data=json.dumps(
                    {
                        "type": "expense",
                        "amount": 10 + i,
                        "account_id": tx_api_data["egp_id"],
                        "category_id": tx_api_data["cat_id"],
                        "date": "2026-03-19",
                    }
                ),
                content_type="application/json",
            )

        resp = c.get("/api/transactions?limit=2")
        assert resp.status_code == 200
        body = json.loads(resp.content)
        assert len(body["results"]) == 2
        assert body["has_next"] is True

    def test_list_with_offset_pagination(self, client, tx_api_data):
        c = set_auth_cookie(client, tx_api_data["session_token"])
        # Create 5 transactions
        for i in range(5):
            c.post(
                "/api/transactions",
                data=json.dumps(
                    {
                        "type": "expense",
                        "amount": 10 + i,
                        "account_id": tx_api_data["egp_id"],
                        "category_id": tx_api_data["cat_id"],
                        "date": "2026-03-19",
                    }
                ),
                content_type="application/json",
            )

        # First page: limit=2, offset=0
        resp = c.get("/api/transactions?limit=2&offset=0")
        assert resp.status_code == 200
        page1 = json.loads(resp.content)
        assert len(page1["results"]) == 2
        assert page1["has_next"] is True
        assert page1["has_previous"] is False
        assert page1["total_count"] == 5
        page1_ids = {tx["id"] for tx in page1["results"]}

        # Second page: limit=2, offset=2
        resp = c.get("/api/transactions?limit=2&offset=2")
        assert resp.status_code == 200
        page2 = json.loads(resp.content)
        assert len(page2["results"]) == 2
        assert page2["has_next"] is True
        assert page2["has_previous"] is True
        assert page2["total_count"] == 5
        page2_ids = {tx["id"] for tx in page2["results"]}

        # Verify pages have different transactions
        assert page1_ids != page2_ids, (
            "Page 1 and page 2 should have different transactions"
        )

    def test_transfer(self, client, tx_api_data):
        from decimal import Decimal

        c = set_auth_cookie(client, tx_api_data["session_token"])

        # Create a second EGP account for same-currency transfer
        egp2 = AccountFactory(
            user_id=tx_api_data["user_id"],
            institution_id=tx_api_data["inst_id"],
            name="EGP Savings 2",
            currency="EGP",
            current_balance=5000,
            initial_balance=5000,
        )
        egp2_id = str(egp2.id)

        resp = c.post(
            "/api/transactions/transfer",
            data=json.dumps(
                {
                    "source_account_id": tx_api_data["egp_id"],
                    "dest_account_id": egp2_id,
                    "amount": 1000,
                    "date": "2026-03-19",
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 201
        body = json.loads(resp.content)
        assert "debit" in body
        assert "credit" in body
        assert Decimal(body["debit"]["balance_delta"]) == Decimal("-1000")
        assert Decimal(body["credit"]["balance_delta"]) == Decimal("1000")

    def test_exchange(self, client, tx_api_data):
        c = set_auth_cookie(client, tx_api_data["session_token"])
        resp = c.post(
            "/api/transactions/exchange",
            data=json.dumps(
                {
                    "source_account_id": tx_api_data["usd_id"],
                    "dest_account_id": tx_api_data["egp_id"],
                    "amount": 100,
                    "rate": 50.5,
                    "date": "2026-03-19",
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 201
        body = json.loads(resp.content)
        assert "debit" in body
        assert "credit" in body

    def test_create_invalid_json(self, client, tx_api_data):
        c = set_auth_cookie(client, tx_api_data["session_token"])
        resp = c.post(
            "/api/transactions",
            data="not json",
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_unauthenticated(self, client):
        resp = client.get("/api/transactions")
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# Transfer API error paths
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestApiTransactionTransferErrors:
    """Error-path tests for POST /api/transactions/transfer."""

    def test_missing_source_account_returns_error(
        self, client: Client, tx_api_data: dict[str, str]
    ) -> None:
        """Omitting source_account_id triggers a 400 with error message."""
        c = set_auth_cookie(client, tx_api_data["session_token"])
        resp = c.post(
            "/api/transactions/transfer",
            data=json.dumps(
                {
                    "dest_account_id": tx_api_data["egp_id"],
                    "amount": 500,
                    "date": "2026-03-25",
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 400
        body = json.loads(resp.content)
        assert "error" in body

    def test_missing_amount_returns_error(
        self, client: Client, tx_api_data: dict[str, str]
    ) -> None:
        """Omitting amount defaults to 0, which the service rejects."""
        c = set_auth_cookie(client, tx_api_data["session_token"])
        # Create a second EGP account for valid source/dest pair
        egp2 = AccountFactory(
            user_id=tx_api_data["user_id"],
            institution_id=tx_api_data["inst_id"],
            name="EGP Extra",
            currency="EGP",
            current_balance=5000,
            initial_balance=5000,
        )
        egp2_id = str(egp2.id)

        resp = c.post(
            "/api/transactions/transfer",
            data=json.dumps(
                {
                    "source_account_id": tx_api_data["egp_id"],
                    "dest_account_id": egp2_id,
                    "date": "2026-03-25",
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 400
        body = json.loads(resp.content)
        assert "error" in body

    def test_zero_amount_returns_error(
        self, client: Client, tx_api_data: dict[str, str]
    ) -> None:
        """Explicit amount=0 is rejected as non-positive."""
        c = set_auth_cookie(client, tx_api_data["session_token"])
        egp2 = AccountFactory(
            user_id=tx_api_data["user_id"],
            institution_id=tx_api_data["inst_id"],
            name="EGP Extra 2",
            currency="EGP",
            current_balance=5000,
            initial_balance=5000,
        )
        egp2_id = str(egp2.id)

        resp = c.post(
            "/api/transactions/transfer",
            data=json.dumps(
                {
                    "source_account_id": tx_api_data["egp_id"],
                    "dest_account_id": egp2_id,
                    "amount": 0,
                    "date": "2026-03-25",
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 400
        body = json.loads(resp.content)
        assert "error" in body
        assert "positive" in body["error"].lower()


# ---------------------------------------------------------------------------
# Exchange API error paths
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestApiTransactionExchangeErrors:
    """Error-path tests for POST /api/transactions/exchange."""

    def test_missing_fields_returns_error(
        self, client: Client, tx_api_data: dict[str, str]
    ) -> None:
        """Omitting required fields (source/dest) triggers a 400."""
        c = set_auth_cookie(client, tx_api_data["session_token"])
        resp = c.post(
            "/api/transactions/exchange",
            data=json.dumps({"amount": 100, "rate": 50.5}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        body = json.loads(resp.content)
        assert "error" in body

    def test_zero_amount_returns_error(
        self, client: Client, tx_api_data: dict[str, str]
    ) -> None:
        """Exchange with amount=0 is rejected."""
        c = set_auth_cookie(client, tx_api_data["session_token"])
        resp = c.post(
            "/api/transactions/exchange",
            data=json.dumps(
                {
                    "source_account_id": tx_api_data["usd_id"],
                    "dest_account_id": tx_api_data["egp_id"],
                    "amount": 0,
                    "rate": 50.5,
                    "date": "2026-03-25",
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 400
        body = json.loads(resp.content)
        assert "error" in body
