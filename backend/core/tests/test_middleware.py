"""Tests for TimezoneMiddleware, LanguageMiddleware and context processors."""

import zoneinfo

import pytest
from django.http import HttpResponse
from django.test import RequestFactory
from django.utils import translation

from core.context_processors import active_tab, currency_preferences
from core.middleware import LanguageMiddleware, TimezoneMiddleware
from tests.factories import CurrencyFactory, UserCurrencyPreferenceFactory, UserFactory


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


class TestLanguageMiddleware:
    """LanguageMiddleware activates user language preference during request processing."""

    @pytest.mark.django_db
    def test_authenticated_user_gets_their_language(self) -> None:
        user = UserFactory(language="ar")

        factory = RequestFactory()
        request = factory.get("/")
        request.user_id = str(user.id)  # type: ignore[attr-defined]

        def get_response(req: object) -> HttpResponse:
            assert translation.get_language() == "ar"
            return HttpResponse("ok")

        middleware = LanguageMiddleware(get_response)
        response = middleware(request)
        assert response.status_code == 200


class TestCurrencyPreferencesContext:
    def test_anonymous_request_uses_safe_defaults(self) -> None:
        factory = RequestFactory()
        request = factory.get("/")

        result = currency_preferences(request)

        assert result["active_currencies"] == []
        assert result["selected_display_currency"] == "EGP"
        assert result["display_currency"].selected_currency == "EGP"

    @pytest.mark.django_db
    def test_authenticated_request_exposes_effective_display_currency(self) -> None:
        CurrencyFactory(code="EGP", name="Egyptian Pound", display_order=0)
        CurrencyFactory(code="EUR", name="Euro", display_order=1)
        user = UserFactory()
        UserCurrencyPreferenceFactory(
            user=user,
            active_currency_codes=["EUR", "BOGUS"],
            selected_display_currency="USD",
        )

        factory = RequestFactory()
        request = factory.get("/")
        request.user_id = str(user.id)  # type: ignore[attr-defined]

        result = currency_preferences(request)

        assert [currency.code for currency in result["active_currencies"]] == ["EUR"]
        assert result["selected_display_currency"] == "EUR"
        assert result["display_currency"].selected_currency == "EUR"

    @pytest.mark.django_db
    def test_authenticated_user_default_english(self) -> None:
        user = UserFactory(language="en")

        factory = RequestFactory()
        request = factory.get("/")
        request.user_id = str(user.id)  # type: ignore[attr-defined]

        def get_response(req: object) -> HttpResponse:
            assert translation.get_language() == "en"
            return HttpResponse("ok")

        middleware = LanguageMiddleware(get_response)
        response = middleware(request)
        assert response.status_code == 200

    def test_anonymous_falls_back_to_accept_language(self) -> None:
        factory = RequestFactory()
        request = factory.get("/", HTTP_ACCEPT_LANGUAGE="ar,en-US;q=0.9,en;q=0.8")

        def get_response(req: object) -> HttpResponse:
            assert translation.get_language() == "ar"
            return HttpResponse("ok")

        middleware = LanguageMiddleware(get_response)
        response = middleware(request)
        assert response.status_code == 200

    def test_anonymous_falls_back_to_english(self) -> None:
        factory = RequestFactory()
        request = factory.get("/")

        def get_response(req: object) -> HttpResponse:
            assert translation.get_language() == "en"
            return HttpResponse("ok")

        middleware = LanguageMiddleware(get_response)
        response = middleware(request)
        assert response.status_code == 200

    def test_anonymous_no_ar_in_accept_language(self) -> None:
        factory = RequestFactory()
        request = factory.get("/", HTTP_ACCEPT_LANGUAGE="fr,de")

        def get_response(req: object) -> HttpResponse:
            assert translation.get_language() == "en"
            return HttpResponse("ok")

        middleware = LanguageMiddleware(get_response)
        response = middleware(request)
        assert response.status_code == 200
