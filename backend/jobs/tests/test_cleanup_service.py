"""
Tests for CleanupService — expired token and session deletion.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from auth_app.models import AuthToken, Session
from jobs.services.cleanup import CleanupService
from tests.factories import SessionFactory, UserFactory


@pytest.mark.django_db(transaction=True)
class TestCleanupService:
    """Tests for CleanupService.cleanup()."""

    def setup_method(self) -> None:
        self.svc = CleanupService()
        self.user = UserFactory()

    def test_deletes_expired_tokens(self) -> None:
        """Expired auth tokens are removed."""
        AuthToken.objects.create(
            email=self.user.email,
            token="expired-token-1",
            expires_at=timezone.now() - timedelta(hours=1),
        )
        tokens, sessions = self.svc.cleanup()
        assert tokens >= 1
        assert not AuthToken.objects.filter(token="expired-token-1").exists()

    def test_deletes_expired_sessions(self) -> None:
        """Expired sessions are removed."""
        SessionFactory(
            user=self.user,
            token="expired-session-1",
            expires_at=timezone.now() - timedelta(hours=1),
        )
        tokens, sessions = self.svc.cleanup()
        assert sessions >= 1
        assert not Session.objects.filter(token="expired-session-1").exists()

    def test_preserves_valid_tokens_and_sessions(self) -> None:
        """Valid (future-expiring) tokens and sessions are NOT deleted."""
        AuthToken.objects.create(
            email=self.user.email,
            token="valid-token-1",
            expires_at=timezone.now() + timedelta(days=1),
        )
        valid_session = SessionFactory(
            user=self.user,
            token="valid-session-1",
            expires_at=timezone.now() + timedelta(days=30),
        )
        self.svc.cleanup()
        assert AuthToken.objects.filter(token="valid-token-1").exists()
        assert Session.objects.filter(id=valid_session.id).exists()

    def test_returns_correct_counts(self) -> None:
        """Returned tuple reflects actual deletions."""
        AuthToken.objects.create(
            email=self.user.email,
            token="count-token-1",
            expires_at=timezone.now() - timedelta(hours=1),
        )
        AuthToken.objects.create(
            email=self.user.email,
            token="count-token-2",
            expires_at=timezone.now() - timedelta(hours=2),
        )
        tokens, _ = self.svc.cleanup()
        assert tokens >= 2


@pytest.mark.django_db(transaction=True)
class TestCleanupEmptyTables:
    """Verify cleanup handles empty tables gracefully."""

    def test_cleanup_on_empty_tables(self) -> None:
        """Cleanup with no expired tokens/sessions returns (0, 0) without error."""  # gap: data
        svc = CleanupService()
        tokens, sessions = svc.cleanup()
        assert tokens == 0
        assert sessions == 0
