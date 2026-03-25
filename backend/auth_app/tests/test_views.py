"""
Tests for auth views — unified auth, verify, logout page handlers.

Integration tests hitting real DB.
"""

import time
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from auth_app.services import SESSION_COOKIE_NAME
from core.models import AuthToken, Category, Session, User
from tests.factories import AuthTokenFactory, SessionFactory, UserFactory

# ---------------------------------------------------------------------------
# Unified Auth (/login)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestUnifiedAuthPage:
    def test_get_renders_form(self, client: Client) -> None:
        """GET /login renders unified auth page with email form."""
        response = client.get("/login")
        assert response.status_code == 200
        content = response.content.decode()
        assert "sign in or create an account" in content
        assert 'name="email"' in content
        assert 'name="website"' in content  # honeypot field
        assert 'name="_rt"' in content  # timing field

    def test_existing_email_sends_login_link(self, client: Client) -> None:
        """Existing user → sends login link → check_email (not new user)."""
        user = UserFactory(email="unified-login@example.com")
        response = client.post(
            "/login",
            {
                "email": "unified-login@example.com",
                "_rt": str(int(time.time()) - 5),
            },
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "Check your email" in content
        assert "unified-login@example.com" in content
        # Should NOT show "Welcome to ClearMoney" (existing user)
        assert "Welcome to ClearMoney" not in content
        # Token created with login purpose
        assert AuthToken.objects.filter(
            email="unified-login@example.com", purpose="login"
        ).exists()
        # Cleanup
        AuthToken.objects.filter(email="unified-login@example.com").delete()
        User.objects.filter(id=user.id).delete()

    def test_new_email_sends_registration_link(self, client: Client) -> None:
        """New email → sends registration link → check_email with welcome."""
        response = client.post(
            "/login",
            {
                "email": "unified-new@example.com",
                "_rt": str(int(time.time()) - 5),
            },
        )
        assert response.status_code == 200
        content = response.content.decode()
        # New users get welcome message
        assert "Welcome to ClearMoney" in content
        assert "unified-new@example.com" in content
        # Token created with registration purpose
        assert AuthToken.objects.filter(
            email="unified-new@example.com", purpose="registration"
        ).exists()
        # Cleanup
        AuthToken.objects.filter(email="unified-new@example.com").delete()

    def test_both_cases_show_check_email(self, client: Client) -> None:
        """Both existing and new emails always render check_email page."""
        user = UserFactory(email="both-test@example.com")
        # Existing user
        resp1 = client.post(
            "/login",
            {"email": "both-test@example.com", "_rt": str(int(time.time()) - 5)},
        )
        assert b"Check your email" in resp1.content
        # Clean up token to avoid cooldown
        AuthToken.objects.filter(email="both-test@example.com").delete()

        # New user
        resp2 = client.post(
            "/login",
            {"email": "brand-new-both@example.com", "_rt": str(int(time.time()) - 5)},
        )
        content2 = resp2.content.decode()
        # New users see "Welcome to ClearMoney" instead of "Check your email"
        assert "Welcome to ClearMoney" in content2
        # Cleanup
        AuthToken.objects.filter(email="brand-new-both@example.com").delete()
        User.objects.filter(id=user.id).delete()

    def test_empty_email_shows_error(self, client: Client) -> None:
        """Empty email → error on form."""
        response = client.post(
            "/login",
            {"email": "", "_rt": str(int(time.time()) - 5)},
        )
        assert response.status_code == 200
        assert b"Email is required" in response.content

    def test_honeypot_silently_rejects(self, client: Client) -> None:
        """Honeypot filled → silently shows check_email (bot thinks it worked)."""
        response = client.post(
            "/login",
            {
                "email": "bot@example.com",
                "website": "http://spam.com",
                "_rt": str(int(time.time()) - 5),
            },
        )
        assert response.status_code == 200
        assert b"Check your email" in response.content
        # No token created
        assert not AuthToken.objects.filter(email="bot@example.com").exists()


# ---------------------------------------------------------------------------
# Register Redirect
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRegisterRedirect:
    def test_register_redirects_to_login(self, client: Client) -> None:
        """GET /register → 302 redirect to /login."""
        response = client.get("/register")
        assert response.status_code == 302
        assert response.url == "/login"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Verify Magic Link
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestVerifyMagicLink:
    def test_valid_login_token_creates_session(self, client: Client) -> None:
        user = UserFactory(email="verify-login@example.com")
        token = AuthTokenFactory(email="verify-login@example.com", purpose="login")

        response = client.get(f"/auth/verify?token={token.token}")
        assert response.status_code == 302
        assert response.url == "/"  # type: ignore[attr-defined]

        # Session cookie set
        assert SESSION_COOKIE_NAME in response.cookies

        # Session exists in DB
        session_token = response.cookies[SESSION_COOKIE_NAME].value
        assert Session.objects.filter(token=session_token).exists()

        # Cleanup
        Session.objects.filter(token=session_token).delete()
        AuthToken.objects.filter(id=token.id).delete()
        User.objects.filter(id=user.id).delete()

    def test_valid_registration_token_creates_user_and_categories(
        self, client: Client
    ) -> None:
        token = AuthTokenFactory(email="new-verify@example.com", purpose="registration")

        response = client.get(f"/auth/verify?token={token.token}")
        assert response.status_code == 302
        assert response.url == "/"  # type: ignore[attr-defined]

        # User created
        user = User.objects.get(email="new-verify@example.com")

        # Categories seeded (23 defaults — type-agnostic)
        cat_count = Category.objects.filter(user_id=user.id).count()
        assert cat_count == 27

        # Cleanup
        session_token = response.cookies[SESSION_COOKIE_NAME].value
        Category.objects.filter(user_id=user.id).delete()
        Session.objects.filter(token=session_token).delete()
        AuthToken.objects.filter(id=token.id).delete()
        User.objects.filter(id=user.id).delete()

    def test_expired_token_shows_link_expired(self, client: Client) -> None:
        token = AuthTokenFactory(
            email="expired@example.com",
            purpose="login",
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        response = client.get(f"/auth/verify?token={token.token}")
        assert response.status_code == 200
        assert b"Link expired" in response.content
        # Cleanup
        AuthToken.objects.filter(id=token.id).delete()

    def test_used_token_shows_link_expired(self, client: Client) -> None:
        token = AuthTokenFactory(email="used@example.com", purpose="login", used=True)
        response = client.get(f"/auth/verify?token={token.token}")
        assert response.status_code == 200
        assert (
            b"Link expired" in response.content
            or b"already been used" in response.content
        )
        # Cleanup
        AuthToken.objects.filter(id=token.id).delete()

    def test_missing_token_shows_link_expired(self, client: Client) -> None:
        response = client.get("/auth/verify")
        assert response.status_code == 200
        assert b"Link expired" in response.content

    def test_invalid_token_shows_link_expired(self, client: Client) -> None:
        response = client.get("/auth/verify?token=totally-invalid")
        assert response.status_code == 200
        assert b"Link expired" in response.content


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestLogout:
    def test_logout_clears_session(self, client: Client) -> None:
        user = UserFactory()
        session = SessionFactory(user=user)
        client.cookies[SESSION_COOKIE_NAME] = session.token

        response = client.post("/logout")
        assert response.status_code == 302
        assert response.url == "/login"  # type: ignore[attr-defined]

        # Session deleted from DB
        assert not Session.objects.filter(token=session.token).exists()

        # Cookie cleared
        cookie = response.cookies.get(SESSION_COOKIE_NAME)
        assert cookie is not None
        assert cookie.value == ""

        # Cleanup
        User.objects.filter(id=user.id).delete()

    def test_logout_without_cookie_still_redirects(self, client: Client) -> None:
        response = client.post("/logout")
        assert response.status_code == 302
        assert response.url == "/login"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Invalid Email Format
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestInvalidEmailFormat:
    """Verify login rejects malformed email inputs."""  # gap: data

    def test_login_empty_email_shows_error(self, client: Client) -> None:
        """POST /login with empty email renders an error message."""  # gap: data
        response = client.post(
            "/login",
            {
                "email": "",
                "_rt": str(int(time.time()) - 5),
            },
        )
        assert response.status_code == 200
        assert b"Email is required" in response.content

    def test_login_whitespace_email_shows_error(self, client: Client) -> None:
        """POST /login with whitespace-only email renders an error message."""  # gap: data
        response = client.post(
            "/login",
            {
                "email": "   ",
                "_rt": str(int(time.time()) - 5),
            },
        )
        assert response.status_code == 200
        assert b"Email is required" in response.content
