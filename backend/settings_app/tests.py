"""
Settings app tests — settings page rendering and CSV export.

Tests create real users and sessions in the database (integration tests),
matching Go's handler test pattern with testutil.SetupAuth().

Uses TransactionTestCase because we insert raw SQL outside Django's
transaction wrapper (Go owns the schema).
"""

import uuid
from datetime import timedelta

from django.db import connection
from django.test import TransactionTestCase
from django.utils import timezone

from core.middleware import COOKIE_NAME


class SettingsPageTest(TransactionTestCase):
    """Tests for GET /settings — settings page rendering."""

    def setUp(self):
        """Create test user and session."""
        self.user_id = str(uuid.uuid4())
        self.user_email = f'settings-{uuid.uuid4().hex[:8]}@example.com'
        self.session_token = str(uuid.uuid4())

        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO users (id, email) VALUES (%s, %s)",
                [self.user_id, self.user_email],
            )
            cursor.execute(
                "INSERT INTO sessions (id, user_id, token, expires_at) VALUES (%s, %s, %s, %s)",
                [str(uuid.uuid4()), self.user_id, self.session_token, timezone.now() + timedelta(days=30)],
            )

    def tearDown(self):
        """Clean up test data."""
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM sessions WHERE user_id = %s", [self.user_id])
            cursor.execute("DELETE FROM users WHERE id = %s", [self.user_id])

    def test_settings_returns_200(self):
        """Authenticated request to /settings should return 200."""
        response = self.client.get('/settings', **{
            'HTTP_COOKIE': f'{COOKIE_NAME}={self.session_token}',
        })
        self.assertEqual(response.status_code, 200)

    def test_settings_contains_key_elements(self):
        """Settings page should contain dark mode, export, notifications, and logout."""
        response = self.client.get('/settings', **{
            'HTTP_COOKIE': f'{COOKIE_NAME}={self.session_token}',
        })
        content = response.content.decode()
        self.assertIn('Dark Mode', content)
        self.assertIn('Export Transactions', content)
        self.assertIn('Push Notifications', content)
        self.assertIn('Log Out', content)

    def test_settings_contains_quick_links(self):
        """Settings page should contain quick links to other features."""
        response = self.client.get('/settings', **{
            'HTTP_COOKIE': f'{COOKIE_NAME}={self.session_token}',
        })
        content = response.content.decode()
        self.assertIn('/budgets', content)
        self.assertIn('/investments', content)
        self.assertIn('/recurring', content)

    def test_settings_redirects_without_auth(self):
        """Unauthenticated request should redirect to /login."""
        response = self.client.get('/settings')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/login')


class ExportTransactionsTest(TransactionTestCase):
    """Tests for GET /export/transactions — CSV export."""

    def setUp(self):
        """Create test user and session."""
        self.user_id = str(uuid.uuid4())
        self.user_email = f'export-{uuid.uuid4().hex[:8]}@example.com'
        self.session_token = str(uuid.uuid4())

        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO users (id, email) VALUES (%s, %s)",
                [self.user_id, self.user_email],
            )
            cursor.execute(
                "INSERT INTO sessions (id, user_id, token, expires_at) VALUES (%s, %s, %s, %s)",
                [str(uuid.uuid4()), self.user_id, self.session_token, timezone.now() + timedelta(days=30)],
            )

    def tearDown(self):
        """Clean up test data."""
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM sessions WHERE user_id = %s", [self.user_id])
            cursor.execute("DELETE FROM users WHERE id = %s", [self.user_id])

    def test_export_returns_csv(self):
        """Export with valid dates should return CSV with correct headers."""
        response = self.client.get(
            '/export/transactions?from=2026-01-01&to=2026-03-31',
            **{'HTTP_COOKIE': f'{COOKIE_NAME}={self.session_token}'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('transactions_', response['Content-Disposition'])

    def test_export_csv_header_row(self):
        """CSV should contain the expected header row."""
        response = self.client.get(
            '/export/transactions?from=2026-01-01&to=2026-03-31',
            **{'HTTP_COOKIE': f'{COOKIE_NAME}={self.session_token}'},
        )
        content = response.content.decode()
        first_line = content.split('\r\n')[0]
        self.assertEqual(
            first_line,
            'Date,Type,Amount,Currency,Account ID,Category ID,Note,Created At',
        )

    def test_export_invalid_dates_returns_400(self):
        """Invalid date parameters should return 400."""
        response = self.client.get(
            '/export/transactions?from=invalid&to=also-invalid',
            **{'HTTP_COOKIE': f'{COOKIE_NAME}={self.session_token}'},
        )
        self.assertEqual(response.status_code, 400)

    def test_export_missing_dates_returns_400(self):
        """Missing date parameters should return 400."""
        response = self.client.get(
            '/export/transactions',
            **{'HTTP_COOKIE': f'{COOKIE_NAME}={self.session_token}'},
        )
        self.assertEqual(response.status_code, 400)

    def test_export_redirects_without_auth(self):
        """Unauthenticated export should redirect to /login."""
        response = self.client.get('/export/transactions?from=2026-01-01&to=2026-03-31')
        self.assertEqual(response.status_code, 302)
