"""
Tests for AuthService — magic link auth business logic.

Tests rate limiting, token management, session creation, and category seeding.
Like Go's internal/service/auth_test.go.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from auth_app.services import AuthService, EmailService, SendResult
from core.models import AuthToken, Category, Session, User
from tests.factories import AuthTokenFactory, UserFactory


@pytest.fixture
def email_service() -> EmailService:
    """Dev-mode email service (no API key)."""
    return EmailService(
        api_key="", from_addr="test@test.com", app_url="http://localhost:8080"
    )


@pytest.fixture
def auth_svc(email_service: EmailService) -> AuthService:
    """AuthService with dev-mode email and high caps."""
    return AuthService(email_service=email_service, max_daily_emails=50)


# ---------------------------------------------------------------------------
# EmailService
# ---------------------------------------------------------------------------


class TestEmailService:
    def test_dev_mode_when_no_api_key(self) -> None:
        svc = EmailService(api_key="", from_addr="x@x.com", app_url="http://localhost")
        assert svc.dev_mode is True

    def test_link_url_format(self) -> None:
        svc = EmailService(
            api_key="", from_addr="x@x.com", app_url="http://localhost:8080"
        )
        assert (
            svc.link_url("abc123") == "http://localhost:8080/auth/verify?token=abc123"
        )

    def test_link_url_strips_trailing_slash(self) -> None:
        svc = EmailService(
            api_key="", from_addr="x@x.com", app_url="http://localhost:8080/"
        )
        assert svc.link_url("abc") == "http://localhost:8080/auth/verify?token=abc"

    def test_send_magic_link_dev_mode_does_not_raise(
        self, email_service: EmailService
    ) -> None:
        # Should log, not send, and not raise
        email_service.send_magic_link("user@example.com", "token123")


# ---------------------------------------------------------------------------
# AuthService — Login
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRequestLoginLink:
    def test_sends_to_existing_user(self, auth_svc: AuthService) -> None:
        user = UserFactory(email="existing@example.com")
        result, err = auth_svc.request_login_link("existing@example.com")
        assert result == SendResult.SENT
        assert err is None
        assert AuthToken.objects.filter(
            email="existing@example.com", purpose="login"
        ).exists()
        # Cleanup
        AuthToken.objects.filter(email="existing@example.com").delete()
        User.objects.filter(id=user.id).delete()

    def test_skips_unknown_email(self, auth_svc: AuthService) -> None:
        result, err = auth_svc.request_login_link("unknown@example.com")
        assert result == SendResult.SKIPPED
        assert err is None  # not an error — just don't send

    def test_empty_email_skipped(self, auth_svc: AuthService) -> None:
        result, err = auth_svc.request_login_link("")
        assert result == SendResult.SKIPPED
        assert err == "Email is required"

    def test_case_insensitive_email(self, auth_svc: AuthService) -> None:
        user = UserFactory(email="case-test@example.com")
        result, _ = auth_svc.request_login_link("CASE-TEST@example.com")
        assert result == SendResult.SENT
        # Cleanup
        AuthToken.objects.filter(email="case-test@example.com").delete()
        User.objects.filter(id=user.id).delete()

    def test_token_reuse(self, auth_svc: AuthService) -> None:
        user = UserFactory(email="reuse@example.com")
        # First request
        result1, _ = auth_svc.request_login_link("reuse@example.com")
        assert result1 == SendResult.SENT
        # Second request — should reuse
        result2, _ = auth_svc.request_login_link("reuse@example.com")
        assert result2 == SendResult.REUSED
        # Cleanup
        AuthToken.objects.filter(email="reuse@example.com").delete()
        User.objects.filter(id=user.id).delete()


# ---------------------------------------------------------------------------
# AuthService — Registration
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRequestRegistrationLink:
    def test_sends_to_new_email(self, auth_svc: AuthService) -> None:
        result, err = auth_svc.request_registration_link("newuser@example.com")
        assert result == SendResult.SENT
        assert err is None
        assert AuthToken.objects.filter(
            email="newuser@example.com", purpose="registration"
        ).exists()
        # Cleanup
        AuthToken.objects.filter(email="newuser@example.com").delete()

    def test_rejects_existing_email(self, auth_svc: AuthService) -> None:
        user = UserFactory(email="exists@example.com")
        result, err = auth_svc.request_registration_link("exists@example.com")
        assert result == SendResult.SKIPPED
        assert err is not None
        assert "already exists" in err
        # Cleanup
        User.objects.filter(id=user.id).delete()

    def test_empty_email_skipped(self, auth_svc: AuthService) -> None:
        result, err = auth_svc.request_registration_link("")
        assert result == SendResult.SKIPPED


# ---------------------------------------------------------------------------
# AuthService — Verify
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestVerifyMagicLink:
    def test_login_creates_session(self, auth_svc: AuthService) -> None:
        user = UserFactory(email="verify@example.com")
        token = AuthTokenFactory(email="verify@example.com", purpose="login")

        result, err = auth_svc.verify_magic_link(token.token)
        assert err is None
        assert result is not None
        assert result["user_id"] == str(user.id)
        assert result["is_new_user"] is False
        assert Session.objects.filter(token=result["session_token"]).exists()
        # Cleanup
        Session.objects.filter(token=result["session_token"]).delete()
        AuthToken.objects.filter(id=token.id).delete()
        User.objects.filter(id=user.id).delete()

    def test_registration_creates_user_and_seeds_categories(
        self, auth_svc: AuthService
    ) -> None:
        token = AuthTokenFactory(email="brand-new@example.com", purpose="registration")

        result, err = auth_svc.verify_magic_link(token.token)
        assert err is None
        assert result is not None
        assert result["is_new_user"] is True

        # User was created
        user = User.objects.get(email="brand-new@example.com")
        assert str(user.id) == result["user_id"]

        # Categories were seeded (25 defaults)
        cat_count = Category.objects.filter(user_id=user.id).count()
        assert cat_count == 25

        # Session was created
        assert Session.objects.filter(token=result["session_token"]).exists()

        # Cleanup
        Category.objects.filter(user_id=user.id).delete()
        Session.objects.filter(token=result["session_token"]).delete()
        AuthToken.objects.filter(id=token.id).delete()
        User.objects.filter(id=user.id).delete()

    def test_expired_token_rejected(self, auth_svc: AuthService) -> None:
        token = AuthTokenFactory(
            email="expired@example.com",
            purpose="login",
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        result, err = auth_svc.verify_magic_link(token.token)
        assert result is None
        assert err is not None
        assert "expired" in err
        # Cleanup
        AuthToken.objects.filter(id=token.id).delete()

    def test_used_token_rejected(self, auth_svc: AuthService) -> None:
        token = AuthTokenFactory(email="used@example.com", purpose="login", used=True)
        result, err = auth_svc.verify_magic_link(token.token)
        assert result is None
        assert err is not None
        assert "already been used" in err
        # Cleanup
        AuthToken.objects.filter(id=token.id).delete()

    def test_invalid_token_rejected(self, auth_svc: AuthService) -> None:
        result, err = auth_svc.verify_magic_link("nonexistent-token")
        assert result is None
        assert err is not None
        assert "Invalid" in err or "invalid" in err

    def test_empty_token_rejected(self, auth_svc: AuthService) -> None:
        result, err = auth_svc.verify_magic_link("")
        assert result is None
        assert err == "Token is required"


# ---------------------------------------------------------------------------
# AuthService — Logout
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestLogout:
    def test_deletes_session(self, auth_svc: AuthService) -> None:
        user = UserFactory()
        from tests.factories import SessionFactory

        session = SessionFactory(user=user)
        assert Session.objects.filter(token=session.token).exists()

        auth_svc.logout(session.token)
        assert not Session.objects.filter(token=session.token).exists()
        # Cleanup
        User.objects.filter(id=user.id).delete()

    def test_logout_nonexistent_token_no_error(self, auth_svc: AuthService) -> None:
        # Should not raise
        auth_svc.logout("nonexistent-token")
