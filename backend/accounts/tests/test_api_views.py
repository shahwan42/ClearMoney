"""
Institution + Account API view tests — HTTP-level tests for
/api/institutions/* and /api/accounts/* JSON API endpoints.

Port of Go's handler/institution_test.go and handler/account_test.go.
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
def api_data(db):
    """User + session + institution + EGP account."""
    user = UserFactory()
    session = SessionFactory(user=user)
    user_id = str(user.id)
    inst_id = str(uuid.uuid4())
    account_id = str(uuid.uuid4())

    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO institutions (id, user_id, name, type) VALUES (%s, %s, %s, 'bank')",
            [inst_id, user_id, "Fixture Bank"],
        )
        cursor.execute(
            "INSERT INTO accounts (id, user_id, institution_id, name, type, currency,"
            " current_balance, initial_balance)"
            " VALUES (%s, %s, %s, %s, 'savings'::account_type, 'EGP'::currency_type, %s, %s)",
            [account_id, user_id, inst_id, "EGP Savings", 10000, 10000],
        )

    yield {
        "user_id": user_id,
        "session_token": session.token,
        "inst_id": inst_id,
        "account_id": account_id,
    }

    # Cleanup
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM transactions WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM accounts WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM institutions WHERE user_id = %s", [user_id])
    Session.objects.filter(user=user).delete()
    User.objects.filter(id=user.id).delete()


def _auth_client(client: Client, token: str) -> Client:
    client.cookies[COOKIE_NAME] = token
    return client


# ---------------------------------------------------------------------------
# Institution API
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestInstitutionAPI:
    def test_list_with_existing(self, client, api_data):
        c = _auth_client(client, api_data["session_token"])
        resp = c.get("/api/institutions")
        assert resp.status_code == 200
        institutions = json.loads(resp.content)
        assert len(institutions) >= 1
        assert institutions[0]["name"] == "Fixture Bank"
        assert "user_id" in institutions[0]

    def test_crud_lifecycle(self, client, api_data):
        c = _auth_client(client, api_data["session_token"])

        # Create
        resp = c.post(
            "/api/institutions",
            data=json.dumps({"name": "New Bank", "type": "fintech"}),
            content_type="application/json",
        )
        assert resp.status_code == 201
        inst = json.loads(resp.content)
        assert inst["name"] == "New Bank"
        assert inst["type"] == "fintech"
        assert "user_id" in inst
        iid = inst["id"]

        # Get
        resp = c.get(f"/api/institutions/{iid}")
        assert resp.status_code == 200
        assert json.loads(resp.content)["name"] == "New Bank"

        # Update
        resp = c.put(
            f"/api/institutions/{iid}",
            data=json.dumps({"name": "Updated Bank", "type": "bank"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert json.loads(resp.content)["name"] == "Updated Bank"

        # Delete
        resp = c.delete(f"/api/institutions/{iid}")
        assert resp.status_code == 204

        # Verify gone
        resp = c.get(f"/api/institutions/{iid}")
        assert resp.status_code == 404

    def test_create_invalid_json(self, client, api_data):
        c = _auth_client(client, api_data["session_token"])
        resp = c.post(
            "/api/institutions",
            data="not json",
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_create_missing_name(self, client, api_data):
        c = _auth_client(client, api_data["session_token"])
        resp = c.post(
            "/api/institutions",
            data=json.dumps({"name": "", "type": "bank"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_unauthenticated(self, client):
        resp = client.get("/api/institutions")
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# Account API
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAccountAPI:
    def test_list_with_existing(self, client, api_data):
        c = _auth_client(client, api_data["session_token"])
        resp = c.get("/api/accounts")
        assert resp.status_code == 200
        accounts = json.loads(resp.content)
        assert len(accounts) >= 1
        assert accounts[0]["name"] == "EGP Savings"
        assert "user_id" in accounts[0]
        # Computed fields should be stripped
        assert "is_credit_type" not in accounts[0]
        assert "available_credit" not in accounts[0]

    def test_list_filter_by_institution(self, client, api_data):
        c = _auth_client(client, api_data["session_token"])
        resp = c.get(f"/api/accounts?institution_id={api_data['inst_id']}")
        assert resp.status_code == 200
        accounts = json.loads(resp.content)
        assert len(accounts) >= 1

    def test_crud_lifecycle(self, client, api_data):
        c = _auth_client(client, api_data["session_token"])

        # Create
        resp = c.post(
            "/api/accounts",
            data=json.dumps({
                "institution_id": api_data["inst_id"],
                "name": "New Account",
                "type": "savings",
                "currency": "EGP",
                "current_balance": 5000,
                "initial_balance": 5000,
            }),
            content_type="application/json",
        )
        assert resp.status_code == 201
        acc = json.loads(resp.content)
        assert acc["name"] == "New Account"
        assert "user_id" in acc
        aid = acc["id"]

        # Get
        resp = c.get(f"/api/accounts/{aid}")
        assert resp.status_code == 200
        assert json.loads(resp.content)["name"] == "New Account"

        # Update
        resp = c.put(
            f"/api/accounts/{aid}",
            data=json.dumps({"name": "Updated Account"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert json.loads(resp.content)["name"] == "Updated Account"

        # Delete
        resp = c.delete(f"/api/accounts/{aid}")
        assert resp.status_code == 204

        # Verify gone
        resp = c.get(f"/api/accounts/{aid}")
        assert resp.status_code == 404

    def test_get_not_found(self, client, api_data):
        c = _auth_client(client, api_data["session_token"])
        fake_id = str(uuid.uuid4())
        resp = c.get(f"/api/accounts/{fake_id}")
        assert resp.status_code == 404

    def test_unauthenticated(self, client):
        resp = client.get("/api/accounts")
        assert resp.status_code == 302
