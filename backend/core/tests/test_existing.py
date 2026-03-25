"""
Core tests — auth middleware and template tag filters.

Filter tests use plain functions (no DB). Middleware tests use
@pytest.mark.django_db and the auth_user fixture from conftest.py.
"""

import logging
from datetime import date, timedelta

import pytest
from django.http import HttpResponse
from django.test import RequestFactory
from django.utils import timezone

from conftest import SessionFactory
from core.middleware import (
    COOKIE_NAME,
    ExceptionLoggingMiddleware,
    GoSessionAuthMiddleware,
)
from core.templatetags.money import (
    _format_number,
    chart_color,
    conic_gradient,
    format_currency,
    format_date,
    format_date_iso,
    format_egp,
    format_usd,
    neg,
    percentage,
)

# ---------------------------------------------------------------------------
# Template tag / filter tests — no DB, no markers
# ---------------------------------------------------------------------------


def test_format_number_zero():
    assert _format_number(0) == "0.00"


def test_format_number_positive():
    assert _format_number(1234567.89) == "1,234,567.89"


def test_format_number_negative():
    assert _format_number(-42.5) == "-42.50"


def test_format_number_small():
    assert _format_number(0.99) == "0.99"


def test_format_number_large():
    assert _format_number(10000000) == "10,000,000.00"


def test_format_egp():
    assert format_egp(1234.5) == "EGP 1,234.50"


def test_format_usd():
    assert format_usd(99.99) == "$99.99"


def test_format_currency_egp():
    assert format_currency(500, "EGP") == "EGP 500.00"


def test_format_currency_usd():
    assert format_currency(500, "USD") == "$500.00"


def test_format_currency_default_egp():
    """No currency specified defaults to EGP."""
    assert format_currency(100) == "EGP 100.00"


def test_format_currency_case_insensitive():
    assert format_currency(100, "usd") == "$100.00"


def test_neg_positive():
    assert neg(42.5) == -42.5


def test_neg_negative():
    assert neg(-10) == 10.0


def test_percentage_normal():
    assert abs(percentage(25, 100) - 25.0) < 0.001


def test_percentage_zero_total():
    assert percentage(10, 0) == 0.0


def test_chart_color_first():
    assert chart_color(0) == "#0d9488"


def test_chart_color_wraps_around():
    """Index 8 should return the same color as index 0."""
    assert chart_color(8) == chart_color(0)


def test_format_date():
    assert format_date(date(2026, 3, 18)) == "Mar 18, 2026"


def test_format_date_iso():
    assert format_date_iso(date(2026, 1, 5)) == "2026-01-05"


def test_conic_gradient_empty():
    result = conic_gradient([])
    assert "#e2e8f0" in result


def test_conic_gradient_single_segment():
    segments = [{"color": "#0d9488", "percentage": 100}]
    result = conic_gradient(segments)
    assert "#0d9488" in result
    assert "conic-gradient" in result


def test_conic_gradient_multiple_segments():
    segments = [
        {"color": "#0d9488", "percentage": 60},
        {"color": "#dc2626", "percentage": 40},
    ]
    result = conic_gradient(segments)
    assert "#0d9488" in result
    assert "#dc2626" in result


# ---------------------------------------------------------------------------
# Auth middleware tests — need real DB
# ---------------------------------------------------------------------------


def _dummy_response(request):
    return HttpResponse("OK", status=200)


def _make_middleware():
    return GoSessionAuthMiddleware(lambda req: _dummy_response(req))


@pytest.mark.django_db
def test_middleware_public_path_no_auth_required():
    """Public paths (healthz, static) pass through without auth."""
    rf = RequestFactory()
    middleware = _make_middleware()
    response = middleware(rf.get("/healthz"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_middleware_no_cookie_redirects_to_login():
    """Protected path without session cookie redirects to /login."""
    rf = RequestFactory()
    middleware = _make_middleware()
    response = middleware(rf.get("/settings"))
    assert response.status_code == 302
    assert response.url == "/login"


@pytest.mark.django_db
def test_middleware_invalid_token_redirects_to_login():
    """Invalid session token redirects to /login."""
    rf = RequestFactory()
    middleware = _make_middleware()
    request = rf.get("/settings")
    request.COOKIES[COOKIE_NAME] = "invalid-token-12345"
    response = middleware(request)
    assert response.status_code == 302
    assert response.url == "/login"


@pytest.mark.django_db
def test_middleware_valid_token_sets_user_info(auth_user):
    """Valid session token returns 200."""
    user_id, user_email, token = auth_user
    rf = RequestFactory()
    middleware = _make_middleware()
    request = rf.get("/settings")
    request.COOKIES[COOKIE_NAME] = token
    response = middleware(request)
    assert response.status_code == 200


@pytest.mark.django_db
def test_middleware_expired_session_redirects(auth_user):
    """Expired session redirects to /login."""
    user_id, _, _ = auth_user
    expired_token = str(__import__("uuid").uuid4())
    SessionFactory(
        user_id=user_id,
        token=expired_token,
        expires_at=timezone.now() - timedelta(hours=1),
    )
    rf = RequestFactory()
    middleware = _make_middleware()
    request = rf.get("/settings")
    request.COOKIES[COOKIE_NAME] = expired_token
    response = middleware(request)
    assert response.status_code == 302
    assert response.url == "/login"


# ---------------------------------------------------------------------------
# ExceptionLoggingMiddleware tests
# ---------------------------------------------------------------------------


def _make_exception_middleware() -> ExceptionLoggingMiddleware:
    return ExceptionLoggingMiddleware(lambda req: _dummy_response(req))


class TestExceptionLoggingMiddleware:
    """Verify that unhandled exceptions are logged with request context."""

    def test_logs_exception_with_user_info(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Request with user_id logs the user identifier."""
        rf = RequestFactory()
        request = rf.get("/accounts")
        request.user_id = "user-abc-123"  # type: ignore[attr-defined]
        middleware = _make_exception_middleware()
        exc = ValueError("something broke")

        with caplog.at_level(logging.ERROR, logger="core.middleware"):
            middleware.process_exception(request, exc)

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert "/accounts" in record.message
        assert "GET" in record.message
        assert "user-abc-123" in record.message

    def test_logs_anonymous_when_no_user(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Request without user_id attribute logs 'anonymous'."""
        rf = RequestFactory()
        request = rf.get("/dashboard")
        middleware = _make_exception_middleware()
        exc = RuntimeError("oops")

        with caplog.at_level(logging.ERROR, logger="core.middleware"):
            middleware.process_exception(request, exc)

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert "/dashboard" in record.message
        assert "anonymous" in record.message
