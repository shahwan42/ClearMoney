"""
Tests for RefreshViewsService — materialized view refresh.

Uses real PostgreSQL. The views are created by migration 0004.
"""

from typing import Any

import pytest
from django.db.utils import OperationalError
from pytest_mock import MockerFixture

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


@pytest.mark.django_db(transaction=True)
class TestRefreshViewsFallback:
    """Verify CONCURRENT → regular REFRESH fallback logic."""

    def test_concurrent_refresh_fallback(self, mocker: MockerFixture) -> None:
        """When CONCURRENT refresh fails, service falls back to regular REFRESH."""  # gap: functional
        from django.db import connection

        real_cursor = connection.cursor
        call_log: list[str] = []

        class FakeCursor:
            """Wraps a real cursor but raises on CONCURRENTLY statements."""

            def __init__(self) -> None:
                self._ctx = real_cursor()
                self._cursor = self._ctx.__enter__()

            def __enter__(self) -> "FakeCursor":
                return self

            def __exit__(self, *args: object) -> None:
                self._ctx.__exit__(None, None, None)

            def execute(self, sql: str, params: Any = None) -> Any:
                call_log.append(sql)
                if "CONCURRENTLY" in sql:
                    raise OperationalError("cannot refresh concurrently")
                return self._cursor.execute(sql, params)

        mocker.patch("jobs.services.refresh_views.connection.cursor", FakeCursor)

        svc = RefreshViewsService()
        svc.refresh()  # should not raise

        # Each view: CONCURRENT attempted, then regular fallback succeeded
        concurrent_calls = [s for s in call_log if "CONCURRENTLY" in s]
        regular_calls = [
            s
            for s in call_log
            if "REFRESH MATERIALIZED VIEW" in s and "CONCURRENTLY" not in s
        ]
        assert len(concurrent_calls) == 2  # one per view
        assert len(regular_calls) == 2  # fallback for each
