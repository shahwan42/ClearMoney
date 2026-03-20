"""
Push notification view tests — HTTP-level tests for /api/push/* JSON endpoints.

Port of Go's handler/push_test.go (implicit — Go didn't have dedicated push tests).
Tests the 3 JSON API endpoints: vapid-key, subscribe, check.
"""

import json

import pytest
from django.test import Client
from pytest_mock import MockerFixture

# ---------------------------------------------------------------------------
# GET /api/push/vapid-key
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestVapidKey:
    def test_returns_public_key(
        self, auth_client: Client, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("VAPID_PUBLIC_KEY", "test-vapid-key-abc123")
        response = auth_client.get("/api/push/vapid-key")

        assert response.status_code == 200
        data = response.json()
        assert data["publicKey"] == "test-vapid-key-abc123"

    def test_returns_empty_when_not_configured(
        self, auth_client: Client, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("VAPID_PUBLIC_KEY", raising=False)
        response = auth_client.get("/api/push/vapid-key")

        assert response.status_code == 200
        data = response.json()
        assert data["publicKey"] == ""

    def test_requires_auth(self, client: Client) -> None:
        response = client.get("/api/push/vapid-key")
        # Middleware redirects unauthenticated requests to /login
        assert response.status_code == 302
        assert "/login" in response["Location"]


# ---------------------------------------------------------------------------
# POST /api/push/subscribe
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSubscribe:
    def test_returns_ok(self, auth_client: Client) -> None:
        subscription = {
            "endpoint": "https://fcm.googleapis.com/fcm/send/abc123",
            "keys": {
                "p256dh": "BNcRd...",
                "auth": "tBHI...",
            },
        }
        response = auth_client.post(
            "/api/push/subscribe",
            data=json.dumps(subscription),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_rejects_invalid_json(self, auth_client: Client) -> None:
        response = auth_client.post(
            "/api/push/subscribe",
            data="not valid json{{{",
            content_type="application/json",
        )

        assert response.status_code == 400
        data = response.json()
        assert "invalid" in data["error"].lower()

    def test_requires_auth(self, client: Client) -> None:
        response = client.post(
            "/api/push/subscribe",
            data=json.dumps({"endpoint": "https://example.com"}),
            content_type="application/json",
        )
        assert response.status_code == 302


# ---------------------------------------------------------------------------
# GET /api/push/check
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCheckNotifications:
    def test_returns_json_array(
        self, auth_client: Client, mocker: MockerFixture
    ) -> None:
        """With no triggers, returns an empty JSON array."""
        mock_svc = mocker.patch("push.views.NotificationService")
        mock_svc.return_value.get_pending_notifications.return_value = []

        response = auth_client.get("/api/push/check")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_returns_notifications(
        self, auth_client: Client, mocker: MockerFixture
    ) -> None:
        mock_svc = mocker.patch("push.views.NotificationService")
        mock_svc.return_value.get_pending_notifications.return_value = [
            {
                "title": "Budget Warning",
                "body": "Food: 85% used",
                "url": "/budgets",
                "tag": "budget-warning-cat-1",
            },
        ]

        response = auth_client.get("/api/push/check")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Budget Warning"
        assert data[0]["tag"] == "budget-warning-cat-1"

    def test_requires_auth(self, client: Client) -> None:
        response = client.get("/api/push/check")
        assert response.status_code == 302
        assert "/login" in response["Location"]
