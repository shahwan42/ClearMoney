"""
Push notification view tests — HTTP-level tests for /api/push/* JSON endpoints.

Tests the 3 JSON API endpoints: vapid-key, subscribe, check.
"""

import json

import pytest
from django.test import Client
from pytest_mock import MockerFixture  # noqa: F401

import auth_app.models
import push.models

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
    def _mock_svc(self, mocker: MockerFixture) -> None:
        mock_svc = mocker.patch("push.views.NotificationService")
        mock_svc.return_value.generate_and_persist.return_value = {
            "created": 0,
            "updated": 0,
            "resolved": 0,
        }

    def test_returns_empty_when_no_unread(
        self, auth_client: Client, mocker: MockerFixture
    ) -> None:
        self._mock_svc(mocker)
        response = auth_client.get("/api/push/check")
        assert response.status_code == 200
        assert response.json() == []

    def test_returns_unread_notifications_with_id(
        self,
        auth_client: Client,
        auth_user: tuple[str, str, str],
        mocker: MockerFixture,
    ) -> None:
        from auth_app.models import User
        from push.models import Notification

        self._mock_svc(mocker)
        user_id, _, _ = auth_user
        user = User.objects.get(id=user_id)
        notif = Notification.objects.create(
            user=user,
            title="Budget Warning",
            body="Food: 85% used",
            url="/budgets",
            tag="budget-warning-cat-1",
            is_read=False,
        )

        response = auth_client.get("/api/push/check")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["title"] == "Budget Warning"
        assert data[0]["tag"] == "budget-warning-cat-1"
        assert data[0]["id"] == str(notif.id)

    def test_excludes_read_notifications(
        self,
        auth_client: Client,
        auth_user: tuple[str, str, str],
        mocker: MockerFixture,
    ) -> None:
        from auth_app.models import User
        from push.models import Notification

        self._mock_svc(mocker)
        user_id, _, _ = auth_user
        user = User.objects.get(id=user_id)
        Notification.objects.create(
            user=user,
            title="Dismissed",
            body="Already read",
            url="/budgets",
            tag="budget-warning-cat-2",
            is_read=True,
        )

        response = auth_client.get("/api/push/check")

        assert response.status_code == 200
        assert response.json() == []

    def test_priority_order(
        self,
        auth_client: Client,
        auth_user: tuple[str, str, str],
        mocker: MockerFixture,
    ) -> None:
        """CC due appears before budget warning regardless of creation order."""
        from auth_app.models import User
        from push.models import Notification

        self._mock_svc(mocker)
        user_id, _, _ = auth_user
        user = User.objects.get(id=user_id)
        Notification.objects.create(
            user=user,
            title="Budget Warning",
            body="Food: 85% used",
            url="/budgets",
            tag="budget-warning-cat-1",
            is_read=False,
        )
        Notification.objects.create(
            user=user,
            title="CC Due",
            body="Card due tomorrow",
            url="/accounts",
            tag="cc-due-MyCard-2026-05-03",
            is_read=False,
        )

        response = auth_client.get("/api/push/check")

        data = response.json()
        assert len(data) == 2
        assert data[0]["tag"].startswith("cc-due-")
        assert data[1]["tag"].startswith("budget-warning-")

    def test_requires_auth(self, client: Client) -> None:
        response = client.get("/api/push/check")
        assert response.status_code == 302
        assert "/login" in response["Location"]


# ---------------------------------------------------------------------------
# POST /api/push/dismiss/<id>
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDismissNotification:
    def test_marks_notification_as_read(
        self, auth_client: Client, auth_user: tuple[str, str, str]
    ) -> None:
        from auth_app.models import User
        from push.models import Notification

        user_id, _, _ = auth_user
        user = User.objects.get(id=user_id)
        notif = Notification.objects.create(
            user=user,
            title="Alert",
            body="Body",
            url="/budgets",
            tag="budget-exceeded-1",
            is_read=False,
        )

        response = auth_client.post(f"/api/push/dismiss/{notif.id}")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        notif.refresh_from_db()
        assert notif.is_read is True

    def test_returns_404_for_other_users_notification(
        self, auth_client: Client, auth_user: tuple[str, str, str]
    ) -> None:
        from push.models import Notification
        from tests.factories import UserFactory

        other_user = UserFactory()
        notif = Notification.objects.create(
            user=other_user,
            title="Other",
            body="Body",
            url="/",
            tag="budget-exceeded-other",
            is_read=False,
        )

        response = auth_client.post(f"/api/push/dismiss/{notif.id}")

        assert response.status_code == 404

    def test_returns_404_for_invalid_uuid(self, auth_client: Client) -> None:
        response = auth_client.post("/api/push/dismiss/not-a-uuid")
        assert response.status_code == 404

    def test_requires_auth(self, client: Client) -> None:
        import uuid

        response = client.post(f"/api/push/dismiss/{uuid.uuid4()}")
        assert response.status_code == 302


# ---------------------------------------------------------------------------
# GET /notifications/badge
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestNotificationBadge:
    def test_badge_shows_unread_count(
        self, auth_client: Client, auth_user: tuple[str, str, str]
    ) -> None:
        from push.models import Notification

        user_id, _, _ = auth_user
        from auth_app.models import User

        user = User.objects.get(id=user_id)
        Notification.objects.create(
            user=user, title="A", body="B", tag="t1", is_read=False
        )
        Notification.objects.create(
            user=user, title="C", body="D", tag="t2", is_read=False
        )

        response = auth_client.get("/notifications/badge")
        assert response.status_code == 200
        assert b"2" in response.content

    def test_badge_empty_when_zero_unread(self, auth_client: Client) -> None:
        response = auth_client.get("/notifications/badge")
        assert response.status_code == 200
        # No badge span when count is 0
        assert b"bg-red-500" not in response.content

    def test_badge_requires_auth(self, client: Client) -> None:
        response = client.get("/notifications/badge")
        assert response.status_code == 302
        assert "/login" in response["Location"]


# ---------------------------------------------------------------------------
# Context processor
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestUnreadNotificationCountContextProcessor:
    def test_count_injected_into_context(
        self, auth_client: Client, auth_user: tuple[str, str, str]
    ) -> None:
        from auth_app.models import User
        from push.models import Notification

        user_id, _, _ = auth_user
        user = User.objects.get(id=user_id)
        Notification.objects.create(
            user=user, title="X", body="Y", tag="cp-t1", is_read=False
        )

        # The dashboard renders the header which uses the context processor
        response = auth_client.get("/")
        assert response.status_code == 200

    def test_unauthenticated_request_returns_empty(self, client: Client) -> None:
        from django.test import RequestFactory

        from push.context_processors import unread_notification_count

        rf = RequestFactory()
        request = rf.get("/")
        # No user_id attribute on plain request
        result = unread_notification_count(request)
        assert result == {}


# ---------------------------------------------------------------------------
# GET /notifications (list page)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestNotificationsPage:
    def test_page_returns_200(self, auth_client: Client) -> None:
        response = auth_client.get("/notifications")
        assert response.status_code == 200

    def test_shows_unread_before_read(
        self, auth_client: Client, auth_user: tuple[str, str, str]
    ) -> None:
        from auth_app.models import User
        from push.models import Notification

        user_id, _, _ = auth_user
        user = User.objects.get(id=user_id)
        Notification.objects.create(
            user=user, title="Read Note", body="Body", tag="r1", is_read=True
        )
        Notification.objects.create(
            user=user, title="Unread Note", body="Body", tag="u1", is_read=False
        )

        response = auth_client.get("/notifications")
        content = response.content.decode()
        # Unread section should appear before Earlier section in DOM
        assert content.index("Unread Note") < content.index("Read Note")

    def test_empty_state_when_no_notifications(self, auth_client: Client) -> None:
        response = auth_client.get("/notifications")
        assert b"No notifications yet" in response.content

    def test_data_isolation_other_user_not_visible(self, auth_client: Client) -> None:
        from push.models import Notification
        from tests.factories import UserFactory

        other_user = UserFactory()
        Notification.objects.create(
            user=other_user, title="Other User", body="Secret", tag="other-t1"
        )
        response = auth_client.get("/notifications")
        assert b"Other User" not in response.content

    def test_requires_auth(self, client: Client) -> None:
        response = client.get("/notifications")
        assert response.status_code == 302
        assert "/login" in response["Location"]


# ---------------------------------------------------------------------------
# POST /notifications/<id>/read (mark single as read)
# POST /notifications/mark-all-read
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestMarkRead:
    def _create_notif(
        self, user: "auth_app.models.User", tag: str = "t1", is_read: bool = False
    ) -> "push.models.Notification":
        from push.models import Notification

        return Notification.objects.create(
            user=user,
            title="Alert",
            body="Details",
            tag=tag,
            is_read=is_read,
            url="/budgets",
        )

    def test_mark_single_read_redirects(
        self, auth_client: Client, auth_user: tuple[str, str, str]
    ) -> None:
        from auth_app.models import User

        user_id, _, _ = auth_user
        user = User.objects.get(id=user_id)
        notif = self._create_notif(user)

        response = auth_client.post(f"/notifications/{notif.id}/read")
        assert response.status_code == 302
        assert response["Location"] == "/budgets"
        notif.refresh_from_db()
        assert notif.is_read is True

    def test_mark_single_read_empty_url_redirects_to_notifications(
        self, auth_client: Client, auth_user: tuple[str, str, str]
    ) -> None:
        from auth_app.models import User
        from push.models import Notification

        user_id, _, _ = auth_user
        user = User.objects.get(id=user_id)
        notif = Notification.objects.create(
            user=user, title="X", body="Y", tag="no-url", url=""
        )

        response = auth_client.post(f"/notifications/{notif.id}/read")
        assert response.status_code == 302
        assert response["Location"] == "/notifications"

    def test_mark_read_already_read_is_idempotent(
        self, auth_client: Client, auth_user: tuple[str, str, str]
    ) -> None:
        from auth_app.models import User

        user_id, _, _ = auth_user
        user = User.objects.get(id=user_id)
        notif = self._create_notif(user, tag="already-read", is_read=True)

        response = auth_client.post(f"/notifications/{notif.id}/read")
        assert response.status_code == 302  # still redirects, no error

    def test_mark_read_returns_404_for_other_users_notification(
        self, auth_client: Client
    ) -> None:
        from tests.factories import UserFactory

        other_user = UserFactory()
        notif = self._create_notif(other_user, tag="other-t2")

        response = auth_client.post(f"/notifications/{notif.id}/read")
        assert response.status_code == 404

    def test_mark_all_read_clears_unread(
        self, auth_client: Client, auth_user: tuple[str, str, str]
    ) -> None:
        from auth_app.models import User
        from push.models import Notification

        user_id, _, _ = auth_user
        user = User.objects.get(id=user_id)
        self._create_notif(user, tag="ma-t1")
        self._create_notif(user, tag="ma-t2")

        response = auth_client.post("/notifications/mark-all-read")
        assert response.status_code == 302
        assert Notification.objects.for_user(user_id).filter(is_read=False).count() == 0

    def test_mark_all_read_empty_is_noop(self, auth_client: Client) -> None:
        response = auth_client.post("/notifications/mark-all-read")
        assert response.status_code == 302

    def test_mark_all_read_htmx_returns_html(
        self, auth_client: Client, auth_user: tuple[str, str, str]
    ) -> None:
        from auth_app.models import User

        user_id, _, _ = auth_user
        user = User.objects.get(id=user_id)
        self._create_notif(user, tag="htmx-t1")

        response = auth_client.post(
            "/notifications/mark-all-read",
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        assert b"Notifications" in response.content
