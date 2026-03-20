"""Tests for TimezoneMiddleware and context processors."""

import zoneinfo

import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from core.context_processors import active_tab
from core.middleware import TimezoneMiddleware


class TestTimezoneMiddleware:
    def test_sets_tz_attribute(self) -> None:
        factory = RequestFactory()
        request = factory.get("/")

        def get_response(req: object) -> HttpResponse:
            assert hasattr(req, "tz")
            assert isinstance(req.tz, zoneinfo.ZoneInfo)
            return HttpResponse("ok")

        middleware = TimezoneMiddleware(get_response)
        middleware(request)

    def test_default_timezone_is_cairo(self) -> None:
        factory = RequestFactory()
        request = factory.get("/")

        def get_response(req: object) -> HttpResponse:
            assert str(req.tz) == "Africa/Cairo"  # type: ignore[attr-defined]
            return HttpResponse("ok")

        middleware = TimezoneMiddleware(get_response)
        middleware(request)


class TestActiveTab:
    """active_tab context processor returns the correct tab for each URL."""

    @pytest.mark.parametrize(
        "path,expected_tab",
        [
            ("/", "home"),
            ("/accounts", "accounts"),
            ("/accounts/123", "accounts"),
            ("/institutions", "accounts"),
            ("/reports", "reports"),
            ("/settings", "more"),
            ("/export/transactions", "more"),
        ],
    )
    def test_tab_for_path(self, path: str, expected_tab: str) -> None:
        factory = RequestFactory()
        request = factory.get(path)
        result = active_tab(request)
        assert result["active_tab"] == expected_tab

    def test_unknown_path_returns_empty(self) -> None:
        factory = RequestFactory()
        request = factory.get("/some-random-path")
        result = active_tab(request)
        assert result["active_tab"] == ""
