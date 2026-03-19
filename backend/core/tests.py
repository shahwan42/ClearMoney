"""
Core tests — auth middleware and template tag filters.

Tests use Django's TransactionTestCase with the real PostgreSQL database.
The middleware tests create test users and sessions directly in the DB,
mirroring Go's testutil.SetupAuth() pattern.

TransactionTestCase is used instead of TestCase because we need raw SQL
inserts outside Django's transaction wrapper (Go owns the schema, not Django).
"""

import uuid
from datetime import timedelta

from django.db import connection
from django.test import RequestFactory, TestCase, TransactionTestCase
from django.utils import timezone

from core.middleware import COOKIE_NAME, GoSessionAuthMiddleware
from core.templatetags.money import (
    _format_number,
    format_currency,
    format_egp,
    format_usd,
    neg,
    percentage,
    chart_color,
    format_date,
    format_date_iso,
    conic_gradient,
)


# ---------------------------------------------------------------------------
# Template tag / filter tests (no DB needed — plain TestCase)
# ---------------------------------------------------------------------------

class FormatNumberTest(TestCase):
    """Tests for _format_number() — thousand separators + 2 decimal places."""

    def test_zero(self):
        self.assertEqual(_format_number(0), '0.00')

    def test_positive(self):
        self.assertEqual(_format_number(1234567.89), '1,234,567.89')

    def test_negative(self):
        self.assertEqual(_format_number(-42.5), '-42.50')

    def test_small(self):
        self.assertEqual(_format_number(0.99), '0.99')

    def test_large(self):
        self.assertEqual(_format_number(10000000), '10,000,000.00')


class FormatCurrencyTest(TestCase):
    """Tests for format_egp, format_usd, format_currency filters."""

    def test_format_egp(self):
        self.assertEqual(format_egp(1234.5), 'EGP 1,234.50')

    def test_format_usd(self):
        self.assertEqual(format_usd(99.99), '$99.99')

    def test_format_currency_egp(self):
        self.assertEqual(format_currency(500, 'EGP'), 'EGP 500.00')

    def test_format_currency_usd(self):
        self.assertEqual(format_currency(500, 'USD'), '$500.00')

    def test_format_currency_default_egp(self):
        """No currency specified defaults to EGP."""
        self.assertEqual(format_currency(100), 'EGP 100.00')

    def test_format_currency_case_insensitive(self):
        self.assertEqual(format_currency(100, 'usd'), '$100.00')


class MathFiltersTest(TestCase):
    """Tests for neg and percentage filters."""

    def test_neg_positive(self):
        self.assertEqual(neg(42.5), -42.5)

    def test_neg_negative(self):
        self.assertEqual(neg(-10), 10.0)

    def test_percentage_normal(self):
        self.assertAlmostEqual(percentage(25, 100), 25.0)

    def test_percentage_zero_total(self):
        self.assertEqual(percentage(10, 0), 0.0)


class ChartColorTest(TestCase):
    """Tests for chart_color filter — 8-color palette with wrapping."""

    def test_first_color(self):
        self.assertEqual(chart_color(0), '#0d9488')

    def test_wraps_around(self):
        """Index 8 should return the same color as index 0."""
        self.assertEqual(chart_color(8), chart_color(0))


class DateFiltersTest(TestCase):
    """Tests for format_date and format_date_iso filters."""

    def test_format_date(self):
        from datetime import date
        d = date(2026, 3, 18)
        self.assertEqual(format_date(d), 'Mar 18, 2026')

    def test_format_date_iso(self):
        from datetime import date
        d = date(2026, 1, 5)
        self.assertEqual(format_date_iso(d), '2026-01-05')


class ConicGradientTest(TestCase):
    """Tests for conic_gradient template tag."""

    def test_empty_segments(self):
        result = conic_gradient([])
        self.assertIn('#e2e8f0', result)

    def test_single_segment(self):
        segments = [{'color': '#0d9488', 'percentage': 100}]
        result = conic_gradient(segments)
        self.assertIn('#0d9488', result)
        self.assertIn('conic-gradient', result)

    def test_multiple_segments(self):
        segments = [
            {'color': '#0d9488', 'percentage': 60},
            {'color': '#dc2626', 'percentage': 40},
        ]
        result = conic_gradient(segments)
        self.assertIn('#0d9488', result)
        self.assertIn('#dc2626', result)


# ---------------------------------------------------------------------------
# Auth middleware tests (need real DB — TransactionTestCase)
# ---------------------------------------------------------------------------

def _create_test_user(cursor):
    """Create a test user and return (user_id, email, session_token).

    Uses plain INSERT (not ON CONFLICT) because the unique index is on
    lower(email), not email directly.
    """
    user_id = str(uuid.uuid4())
    email = f'django-test-{uuid.uuid4().hex[:8]}@example.com'
    token = str(uuid.uuid4())

    cursor.execute(
        "INSERT INTO users (id, email) VALUES (%s, %s)",
        [user_id, email],
    )
    cursor.execute(
        "INSERT INTO sessions (id, user_id, token, expires_at) VALUES (%s, %s, %s, %s)",
        [str(uuid.uuid4()), user_id, token, timezone.now() + timedelta(days=30)],
    )
    return user_id, email, token


def _cleanup_test_user(cursor, user_id):
    """Remove test user and associated sessions."""
    cursor.execute("DELETE FROM sessions WHERE user_id = %s", [user_id])
    cursor.execute("DELETE FROM users WHERE id = %s", [user_id])


class GoSessionAuthMiddlewareTest(TransactionTestCase):
    """
    Tests for GoSessionAuthMiddleware — validates Go session cookies.

    Creates real users and sessions in the database, mirroring Go's
    testutil.SetupAuth() test helper pattern.
    """

    def setUp(self):
        """Create a test user and valid session."""
        self.factory = RequestFactory()
        with connection.cursor() as cursor:
            self.user_id, self.user_email, self.session_token = _create_test_user(cursor)

    def tearDown(self):
        """Clean up test data."""
        with connection.cursor() as cursor:
            _cleanup_test_user(cursor, self.user_id)

    def _get_middleware(self):
        """Create middleware instance with a dummy get_response."""
        return GoSessionAuthMiddleware(lambda req: _dummy_response(req))

    def test_public_path_no_auth_required(self):
        """Public paths (healthz, static) should pass through without auth."""
        middleware = self._get_middleware()
        request = self.factory.get('/healthz')
        response = middleware(request)
        self.assertEqual(response.status_code, 200)

    def test_no_cookie_redirects_to_login(self):
        """Protected path without session cookie should redirect to /login."""
        middleware = self._get_middleware()
        request = self.factory.get('/settings')
        response = middleware(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/login')

    def test_invalid_token_redirects_to_login(self):
        """Invalid session token should redirect and clear cookie."""
        middleware = self._get_middleware()
        request = self.factory.get('/settings')
        request.COOKIES[COOKIE_NAME] = 'invalid-token-12345'
        response = middleware(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/login')

    def test_valid_token_sets_user_info(self):
        """Valid session token should set request.user_id and request.user_email."""
        middleware = self._get_middleware()
        request = self.factory.get('/settings')
        request.COOKIES[COOKIE_NAME] = self.session_token
        response = middleware(request)
        self.assertEqual(response.status_code, 200)

    def test_expired_session_redirects(self):
        """Expired session should redirect to /login."""
        expired_token = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO sessions (id, user_id, token, expires_at) VALUES (%s, %s, %s, %s)",
                [str(uuid.uuid4()), self.user_id, expired_token, timezone.now() - timedelta(hours=1)],
            )

        middleware = self._get_middleware()
        request = self.factory.get('/settings')
        request.COOKIES[COOKIE_NAME] = expired_token
        response = middleware(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/login')


def _dummy_response(request):
    """Dummy view that returns 200 — used to test middleware pass-through."""
    from django.http import HttpResponse
    return HttpResponse('OK', status=200)
