"""
Tests for RefreshViewsService — materialized view refresh.

Uses real PostgreSQL. The views exist because Go migrations created them.
"""

import pytest

from jobs.services.refresh_views import RefreshViewsService


@pytest.mark.django_db(transaction=True)
class TestRefreshViewsService:
    """Tests for RefreshViewsService.refresh()."""

    def test_refresh_succeeds(self) -> None:
        """Refreshing views does not raise an exception."""
        svc = RefreshViewsService()
        svc.refresh()  # should not raise

    def test_refresh_idempotent(self) -> None:
        """Calling refresh() twice is safe (idempotent)."""
        svc = RefreshViewsService()
        svc.refresh()
        svc.refresh()  # second call should also succeed
