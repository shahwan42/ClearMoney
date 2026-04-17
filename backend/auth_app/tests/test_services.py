"""
Tests for AuthService — magic link auth business logic.

Tests rate limiting, token management, session creation, and category seeding.
"""

import secrets
from datetime import timedelta

import freezegun
import pytest
from django.utils import timezone

from auth_app.models import AuthToken, Session, User
from auth_app.services import AuthService, EmailService, SendResult
from categories.models import Category
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

        # Categories were seeded (27 defaults — type-agnostic)
        cat_count = Category.objects.filter(user_id=user.id).count()
        assert cat_count == 27

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


# ---------------------------------------------------------------------------
# AuthService — Unified Access Link
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRequestAccessLink:
    def test_existing_user_sends_login_link(self, auth_svc: AuthService) -> None:
        """Existing email → (SENT, None, False) with purpose=login."""
        user = UserFactory(email="access-existing@example.com")
        result, err, is_new = auth_svc.request_access_link(
            "access-existing@example.com"
        )
        assert result == SendResult.SENT
        assert err is None
        assert is_new is False
        assert AuthToken.objects.filter(
            email="access-existing@example.com", purpose="login"
        ).exists()
        # Cleanup
        AuthToken.objects.filter(email="access-existing@example.com").delete()
        User.objects.filter(id=user.id).delete()

    def test_new_email_sends_registration_link(self, auth_svc: AuthService) -> None:
        """New email → (SENT, None, True) with purpose=registration."""
        result, err, is_new = auth_svc.request_access_link("access-new@example.com")
        assert result == SendResult.SENT
        assert err is None
        assert is_new is True
        assert AuthToken.objects.filter(
            email="access-new@example.com", purpose="registration"
        ).exists()
        # Cleanup
        AuthToken.objects.filter(email="access-new@example.com").delete()

    def test_empty_email_skipped(self, auth_svc: AuthService) -> None:
        """Empty email → (SKIPPED, None, False)."""
        result, err, is_new = auth_svc.request_access_link("")
        assert result == SendResult.SKIPPED
        assert err is None
        assert is_new is False

    def test_reuse_existing_user(self, auth_svc: AuthService) -> None:
        """Existing user with unexpired token → REUSED."""
        user = UserFactory(email="access-reuse@example.com")
        result1, _, _ = auth_svc.request_access_link("access-reuse@example.com")
        assert result1 == SendResult.SENT
        result2, _, is_new = auth_svc.request_access_link("access-reuse@example.com")
        assert result2 == SendResult.REUSED
        assert is_new is False
        # Cleanup
        AuthToken.objects.filter(email="access-reuse@example.com").delete()
        User.objects.filter(id=user.id).delete()


# ---------------------------------------------------------------------------
# AuthService — Rate Limiting
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRateLimiting:
    """Tests for rate limiting logic: per-email cooldown, daily caps, global caps.

    Rate limiting prevents abuse of the magic link endpoint via:
    1. Per-email 5-minute cooldown (1 request per 5 min)
    2. Per-email 3/day limit (max 3 requests per calendar day)
    3. Global 50/day limit (max 50 requests across all emails per day)
    4. Token reuse: unexpired tokens are reused without sending new emails
    5. After expiry, new tokens are generated (not reused)

    All times are in UTC. Calendar days reset at 00:00 UTC.
    """

    def test_cooldown_blocks_second_request(self, auth_svc: AuthService) -> None:
        """Second request within 5 minutes returns COOLDOWN when token is used.

        Scenario:
        - User requests magic link (creates unexpired token)
        - Token is marked as used (e.g., user clicked link or it was consumed)
        - User requests again within 5 minutes
        - Second request returns COOLDOWN (reuse check fails because token is used)
        """
        email = "cooldown@example.com"
        user = UserFactory(email=email)

        # First request — should SEND
        result1, err1 = auth_svc.request_login_link(email)
        assert result1 == SendResult.SENT
        assert err1 is None
        token1 = AuthToken.objects.get(email=email, purpose="login")

        # Mark token as used (simulating user clicking the link)
        token1.used = True
        token1.save()

        # Second request within 5 minutes — should COOLDOWN (reuse fails, cooldown blocks)
        result2, err2 = auth_svc.request_login_link(email)
        assert result2 == SendResult.COOLDOWN
        assert err2 is None
        # No new token should be created (still just 1)
        token_count_after_second = AuthToken.objects.filter(
            email=email, purpose="login"
        ).count()
        assert token_count_after_second == 1

        # Cleanup
        AuthToken.objects.filter(email=email).delete()
        User.objects.filter(id=user.id).delete()

    def test_cooldown_expires_after_5_minutes(self, auth_svc: AuthService) -> None:
        """Request after 5+ minutes succeeds with SENT (cooldown no longer blocks).

        Scenario:
        - User requests magic link at T=0 (token created)
        - Token is marked as used
        - User requests at T=5 min: cooldown blocks (COOLDOWN)
        - User requests at T=5 min + 1 sec: cooldown expired, SENT succeeds
        """
        email = "cooldown-expire@example.com"
        user = UserFactory(email=email)
        now = timezone.now()

        # First request at T=0
        with freezegun.freeze_time(now):
            result1, _ = auth_svc.request_login_link(email)
            assert result1 == SendResult.SENT
            token1 = AuthToken.objects.get(email=email, purpose="login")
            # Mark as used so reuse check fails
            token1.used = True
            token1.save()

        # Request at T=5 min — cooldown still blocks
        with freezegun.freeze_time(now + timedelta(minutes=5)):
            result_at_5min, _ = auth_svc.request_login_link(email)
            assert result_at_5min == SendResult.COOLDOWN

        # Request at T=5 min + 1 sec — cooldown expired, SENT succeeds
        with freezegun.freeze_time(now + timedelta(minutes=5, seconds=1)):
            result2, _ = auth_svc.request_login_link(email)
            assert result2 == SendResult.SENT
            token_count = AuthToken.objects.filter(email=email, purpose="login").count()
            assert token_count == 2  # New token created (cooldown expired)
            # Verify they're different tokens
            tokens = AuthToken.objects.filter(email=email, purpose="login").order_by(
                "created_at"
            )
            assert tokens[0].used is True  # First token was marked used
            assert tokens[1].used is False  # Second token is fresh

        # Cleanup
        AuthToken.objects.filter(email=email).delete()
        User.objects.filter(id=user.id).delete()

    def test_daily_per_email_limit(self, auth_svc: AuthService) -> None:
        """After 3 tokens created in same day, 4th request returns DAILY_LIMIT.

        Scenario:
        - Create 3 login tokens for same user on Day 1 (>5 min apart)
        - Request 4th token on Day 1
        - 4th request returns DAILY_LIMIT
        """
        email = "daily-limit@example.com"
        user = UserFactory(email=email)
        now = timezone.now().replace(hour=12, minute=0, second=0, microsecond=0)

        # Create 3 tokens on the same day, >5 min apart
        # Must mark each as used to prevent reuse blocking the next
        for i in range(3):
            with freezegun.freeze_time(now + timedelta(minutes=i * 6)):
                result, _ = auth_svc.request_login_link(email)
                assert result == SendResult.SENT, f"Request {i + 1} should succeed"
                # Immediately mark as used so next request doesn't reuse it
                token = (
                    AuthToken.objects.filter(email=email, purpose="login")
                    .order_by("-created_at")
                    .first()
                )
                if token:
                    token.used = True
                    token.save(update_fields=["used"])

        # 4th request on same day at T=18min — should hit DAILY_LIMIT
        with freezegun.freeze_time(now + timedelta(minutes=18)):
            result4, _ = auth_svc.request_login_link(email)
            assert result4 == SendResult.DAILY_LIMIT

        # Verify exactly 3 tokens exist for this email on this day
        token_count = AuthToken.objects.filter(email=email, purpose="login").count()
        assert token_count == 3

        # Cleanup
        AuthToken.objects.filter(email=email).delete()
        User.objects.filter(id=user.id).delete()

    def test_daily_counter_resets_next_day(self, auth_svc: AuthService) -> None:
        """Daily limit resets on next calendar day (UTC midnight).

        Scenario:
        - User requests magic link 3 times on Day 1 (each >5 min apart)
        - User requests on Day 2 (after UTC midnight)
        - Day 2 request succeeds (counter reset)
        """
        email = "daily-reset@example.com"
        user = UserFactory(email=email)
        day1 = timezone.now().replace(hour=12, minute=0, second=0, microsecond=0)
        day2 = day1 + timedelta(days=1)

        # Create 3 tokens on Day 1, >5 min apart
        for i in range(3):
            with freezegun.freeze_time(day1 + timedelta(minutes=i * 6)):
                result, _ = auth_svc.request_login_link(email)
                assert result == SendResult.SENT
                # Mark as used so next request doesn't reuse it
                token = (
                    AuthToken.objects.filter(email=email, purpose="login")
                    .order_by("-created_at")
                    .first()
                )
                assert token is not None
                token.used = True
                token.save()

        # Verify daily limit on Day 1
        with freezegun.freeze_time(day1 + timedelta(minutes=18)):
            result, _ = auth_svc.request_login_link(email)
            assert result == SendResult.DAILY_LIMIT

        # On Day 2, counter reset — request succeeds
        with freezegun.freeze_time(day2 + timedelta(hours=1)):
            result, _ = auth_svc.request_login_link(email)
            assert result == SendResult.SENT  # New day, counter reset
            token_count = AuthToken.objects.filter(email=email, purpose="login").count()
            assert token_count == 4  # 3 from day 1 + 1 from day 2

        # Cleanup
        AuthToken.objects.filter(email=email).delete()
        User.objects.filter(id=user.id).delete()

    def test_global_daily_cap(self, auth_svc: AuthService) -> None:
        """Global daily cap blocks requests when exceeded.

        Scenario:
        - Create auth service with global cap of 2 (low for easy testing)
        - Create 2 magic link requests from different emails on same day
        - Request 3 should return GLOBAL_CAP
        """
        # Create auth service with very low global cap for testing
        low_cap_svc = AuthService(email_service=auth_svc.email_svc, max_daily_emails=2)
        now = timezone.now()

        # Create 2 requests from different emails (hitting the cap)
        # Using request_access_link which works for new emails
        for i in range(2):
            with freezegun.freeze_time(now):  # Same time to ensure same day
                result, _, _ = low_cap_svc.request_access_link(
                    f"global-test-{i}@example.com"
                )
                assert result == SendResult.SENT, f"Request {i + 1} should succeed"

        # 3rd request from new email — should hit GLOBAL_CAP
        with freezegun.freeze_time(now):
            result, _, _ = low_cap_svc.request_access_link(
                "global-test-overflow@example.com"
            )
            assert result == SendResult.GLOBAL_CAP

        # Cleanup
        for i in range(2):
            AuthToken.objects.filter(email=f"global-test-{i}@example.com").delete()
            User.objects.filter(email=f"global-test-{i}@example.com").delete()
        AuthToken.objects.filter(email="global-test-overflow@example.com").delete()
        User.objects.filter(email="global-test-overflow@example.com").delete()

    def test_expired_token_allows_new_request_after_cooldown(
        self, auth_svc: AuthService
    ) -> None:
        """Expired token does NOT trigger REUSED; new token generated after cooldown.

        Scenario:
        - User requests magic link at T=0, token expires in 1 min
        - User requests at T=2 min: token is expired, but cooldown still blocks (COOLDOWN)
        - User requests at T=5 min+: token is expired AND cooldown expired → SENT

        This differs from unexpired token reuse (REUSED).
        The key difference: expired tokens don't trigger REUSED, so they're
        subject to normal cooldown rules.
        """
        email = "expired-reuse@example.com"
        user = UserFactory(email=email)
        now = timezone.now()

        # First request — create token with 1-minute TTL
        with freezegun.freeze_time(now):
            # Manually create token with short TTL instead of using service
            AuthToken.objects.create(
                email=email,
                token=secrets.token_urlsafe(32),
                purpose="login",
                used=False,
                expires_at=now + timedelta(minutes=1),
            )
            result1, _ = auth_svc.request_login_link(email)
            # On the second call, first token still valid and unexpired → REUSED
            assert result1 == SendResult.REUSED

        # Request at T=2 min — first token is expired, but cooldown blocks
        with freezegun.freeze_time(now + timedelta(minutes=2)):
            result_at_2min, _ = auth_svc.request_login_link(email)
            assert result_at_2min == SendResult.COOLDOWN

        # Request at T=5 min + 1 sec — token expired AND cooldown expired → SENT
        with freezegun.freeze_time(now + timedelta(minutes=5, seconds=1)):
            result2, _ = auth_svc.request_login_link(email)
            assert result2 == SendResult.SENT
            token_count = AuthToken.objects.filter(email=email, purpose="login").count()
            assert token_count == 2  # Original expired + new fresh token
            # Verify tokens: first is expired, second is fresh
            tokens = AuthToken.objects.filter(email=email, purpose="login").order_by(
                "created_at"
            )
            assert tokens[0].expires_at < now + timedelta(minutes=5, seconds=1)
            assert tokens[1].expires_at > now + timedelta(minutes=5, seconds=1)

        # Cleanup
        AuthToken.objects.filter(email=email).delete()
        User.objects.filter(id=user.id).delete()
