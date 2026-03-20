"""
Tests for auth views — login, register, verify, logout page handlers.

Integration tests hitting real DB. Like Go's handler/auth_test.go.
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
# Login
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestLoginPage:
    def test_get_renders_form(self, client: Client) -> None:
        response = client.get("/login")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Sign in" in content
        assert 'name="email"' in content
        assert 'name="website"' in content  # honeypot field
        assert 'name="_rt"' in content  # timing field

    def test_post_valid_email_shows_check_email(self, client: Client) -> None:
        user = UserFactory(email="login-test@example.com")
        response = client.post(
            "/login",
            {
                "email": "login-test@example.com",
                "_rt": str(int(time.time()) - 5),  # 5 seconds ago
            },
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "Check your email" in content
        assert "login-test@example.com" in content
        # Cleanup
        AuthToken.objects.filter(email="login-test@example.com").delete()
        User.objects.filter(id=user.id).delete()

    def test_post_unknown_email_still_shows_check_email(self, client: Client) -> None:
        """Email enumeration prevention: unknown emails get same response."""
        response = client.post(
            "/login",
            {
                "email": "nonexistent@example.com",
                "_rt": str(int(time.time()) - 5),
            },
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "Check your email" in content
        # Hint should show (since email wasn't sent)
        assert "previously sent link" in content

    def test_post_empty_email_shows_error(self, client: Client) -> None:
        response = client.post(
            "/login",
            {
                "email": "",
                "_rt": str(int(time.time()) - 5),
            },
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "Email is required" in content

    def test_honeypot_silently_rejects(self, client: Client) -> None:
        response = client.post(
            "/login",
            {
                "email": "bot@example.com",
                "website": "http://spam.com",
                "_rt": str(int(time.time()) - 5),
            },
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "Check your email" in content
        # No token should be created
        assert not AuthToken.objects.filter(email="bot@example.com").exists()


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRegisterPage:
    def test_get_renders_form(self, client: Client) -> None:
        response = client.get("/register")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Create account" in content
        assert 'name="email"' in content

    def test_post_new_email_shows_check_email(self, client: Client) -> None:
        response = client.post(
            "/register",
            {
                "email": "newreg@example.com",
                "_rt": str(int(time.time()) - 5),
            },
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "Check your email" in content
        # Cleanup
        AuthToken.objects.filter(email="newreg@example.com").delete()

    def test_post_existing_email_shows_error(self, client: Client) -> None:
        user = UserFactory(email="already@example.com")
        response = client.post(
            "/register",
            {
                "email": "already@example.com",
                "_rt": str(int(time.time()) - 5),
            },
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "already exists" in content
        # Cleanup
        User.objects.filter(id=user.id).delete()

    def test_post_empty_email_shows_error(self, client: Client) -> None:
        response = client.post(
            "/register",
            {
                "email": "",
                "_rt": str(int(time.time()) - 5),
            },
        )
        assert response.status_code == 200
        assert b"Email is required" in response.content

    def test_honeypot_silently_rejects(self, client: Client) -> None:
        response = client.post(
            "/register",
            {
                "email": "bot@example.com",
                "website": "http://spam.com",
                "_rt": str(int(time.time()) - 5),
            },
        )
        assert response.status_code == 200
        assert b"Check your email" in response.content
        assert not AuthToken.objects.filter(email="bot@example.com").exists()


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

        # Categories seeded
        cat_count = Category.objects.filter(user_id=user.id).count()
        assert cat_count == 25

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
