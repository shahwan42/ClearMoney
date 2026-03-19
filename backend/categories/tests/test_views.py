"""
Category API view tests — HTTP-level tests for /api/categories/* JSON API.

Port of Go's handler/category_test.go.
"""

import json

import pytest
from django.db import connection
from django.test import Client

from conftest import SessionFactory, UserFactory
from core.middleware import COOKIE_NAME
from core.models import Session, User


@pytest.fixture
def cat_api_data(db):
    """User + session + seeded system categories."""
    user = UserFactory()
    session = SessionFactory(user=user)
    user_id = str(user.id)

    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO categories (user_id, name, type, icon, is_system, display_order) "
            "VALUES (%s, 'Groceries', 'expense', '🛒', true, 1)",
            [user_id],
        )
        cursor.execute(
            "INSERT INTO categories (user_id, name, type, icon, is_system, display_order) "
            "VALUES (%s, 'Salary', 'income', '💵', true, 1)",
            [user_id],
        )

    yield {
        "user_id": user_id,
        "session_token": session.token,
    }

    # Cleanup
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM categories WHERE user_id = %s", [user_id])
    Session.objects.filter(user=user).delete()
    User.objects.filter(id=user.id).delete()


def _auth_client(client: Client, token: str) -> Client:
    client.cookies[COOKIE_NAME] = token
    return client


@pytest.mark.django_db
class TestCategoryAPI:
    def test_list_seeded(self, client, cat_api_data):
        c = _auth_client(client, cat_api_data["session_token"])
        resp = c.get("/api/categories")
        assert resp.status_code == 200
        cats = json.loads(resp.content)
        assert len(cats) >= 2
        names = [cat["name"] for cat in cats]
        assert "Groceries" in names
        assert "Salary" in names

    def test_filter_by_type(self, client, cat_api_data):
        c = _auth_client(client, cat_api_data["session_token"])
        resp = c.get("/api/categories?type=expense")
        assert resp.status_code == 200
        cats = json.loads(resp.content)
        assert all(cat["type"] == "expense" for cat in cats)

    def test_create_custom(self, client, cat_api_data):
        c = _auth_client(client, cat_api_data["session_token"])
        resp = c.post(
            "/api/categories",
            data=json.dumps({"name": "Custom", "type": "expense", "icon": "🎬"}),
            content_type="application/json",
        )
        assert resp.status_code == 201
        cat = json.loads(resp.content)
        assert cat["name"] == "Custom"
        assert cat["type"] == "expense"
        assert cat["icon"] == "🎬"
        assert cat["is_system"] is False

    def test_create_invalid_type(self, client, cat_api_data):
        c = _auth_client(client, cat_api_data["session_token"])
        resp = c.post(
            "/api/categories",
            data=json.dumps({"name": "Bad", "type": "invalid"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_create_empty_name(self, client, cat_api_data):
        c = _auth_client(client, cat_api_data["session_token"])
        resp = c.post(
            "/api/categories",
            data=json.dumps({"name": "", "type": "expense"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_update_custom(self, client, cat_api_data):
        c = _auth_client(client, cat_api_data["session_token"])
        # Create first
        resp = c.post(
            "/api/categories",
            data=json.dumps({"name": "ToUpdate", "type": "expense"}),
            content_type="application/json",
        )
        cat_id = json.loads(resp.content)["id"]

        # Update
        resp = c.put(
            f"/api/categories/{cat_id}",
            data=json.dumps({"name": "Updated", "icon": "✏️"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert json.loads(resp.content)["name"] == "Updated"

    def test_cannot_modify_system(self, client, cat_api_data):
        c = _auth_client(client, cat_api_data["session_token"])
        cats = json.loads(c.get("/api/categories").content)
        system_cat = next(cat for cat in cats if cat["is_system"])

        resp = c.put(
            f"/api/categories/{system_cat['id']}",
            data=json.dumps({"name": "Renamed"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_archive_custom(self, client, cat_api_data):
        c = _auth_client(client, cat_api_data["session_token"])
        # Create
        resp = c.post(
            "/api/categories",
            data=json.dumps({"name": "ToArchive", "type": "income"}),
            content_type="application/json",
        )
        cat_id = json.loads(resp.content)["id"]

        # Archive (DELETE)
        resp = c.delete(f"/api/categories/{cat_id}")
        assert resp.status_code == 204

        # Should be gone from list
        cats = json.loads(c.get("/api/categories").content)
        assert all(cat["id"] != cat_id for cat in cats)

    def test_cannot_archive_system(self, client, cat_api_data):
        c = _auth_client(client, cat_api_data["session_token"])
        cats = json.loads(c.get("/api/categories").content)
        system_cat = next(cat for cat in cats if cat["is_system"])

        resp = c.delete(f"/api/categories/{system_cat['id']}")
        assert resp.status_code == 400

    def test_unauthenticated(self, client):
        resp = client.get("/api/categories")
        assert resp.status_code == 302  # Redirect to login
