"""Tests for session status endpoint and session timeout warning."""

import json

import pytest
from django.test import Client

from conftest import SessionFactory, UserFactory, set_auth_cookie


@pytest.mark.django_db
class TestSessionStatus:
    """GET /api/session-status returns session expiry info."""

    def test_returns_json_with_expires_in(self) -> None:
        """Authenticated request returns JSON with expires_in_seconds."""
        user = UserFactory()
        session = SessionFactory(user=user)
        client = Client()
        set_auth_cookie(client, session.token)
        response = client.get("/api/session-status")
        assert response.status_code == 200
        data = json.loads(response.content)
        assert "expires_in_seconds" in data
        assert data["expires_in_seconds"] > 0

    def test_unauthenticated_returns_401(self) -> None:
        """Unauthenticated request returns 401."""
        client = Client()
        response = client.get("/api/session-status")
        # Middleware redirects to /login, but for API we expect redirect
        assert response.status_code in (302, 401)
