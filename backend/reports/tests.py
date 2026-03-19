"""
Reports app tests — reports page rendering and data aggregation.

Tests create real users, sessions, accounts, and transactions in the database,
matching Go's integration test pattern with testutil fixtures.

Uses TransactionTestCase for DB tests and plain TestCase for chart builder tests.
"""

import uuid
from datetime import date, timedelta

from django.db import connection
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from core.middleware import COOKIE_NAME
from reports.views import (
    _build_bar_chart,
    _build_chart_segments,
    _get_month_summary,
    _get_spending_by_category,
)


class ReportsPageTest(TransactionTestCase):
    """Tests for GET /reports — reports page rendering."""

    def setUp(self):
        """Create user, session, account, category, and test transactions."""
        self.user_id = str(uuid.uuid4())
        self.user_email = f'reports-{uuid.uuid4().hex[:8]}@example.com'
        self.session_token = str(uuid.uuid4())
        self.account_id = str(uuid.uuid4())
        self.category_id = str(uuid.uuid4())
        self.inst_id = str(uuid.uuid4())
        self._tx_ids = []

        with connection.cursor() as cursor:
            # Create user + session
            cursor.execute(
                "INSERT INTO users (id, email) VALUES (%s, %s)",
                [self.user_id, self.user_email],
            )
            cursor.execute(
                "INSERT INTO sessions (id, user_id, token, expires_at) VALUES (%s, %s, %s, %s)",
                [str(uuid.uuid4()), self.user_id, self.session_token, timezone.now() + timedelta(days=30)],
            )
            # Create institution + account
            cursor.execute(
                "INSERT INTO institutions (id, user_id, name) VALUES (%s, %s, %s)",
                [self.inst_id, self.user_id, 'Test Bank'],
            )
            cursor.execute(
                "INSERT INTO accounts (id, user_id, institution_id, name, type, currency, current_balance) VALUES (%s, %s, %s, %s, 'savings'::account_type, 'EGP'::currency_type, %s)",
                [self.account_id, self.user_id, self.inst_id, 'Test Acct', 10000],
            )
            # Create category
            cursor.execute(
                "INSERT INTO categories (id, user_id, name, type, icon) VALUES (%s, %s, %s, %s, %s)",
                [self.category_id, self.user_id, 'Food', 'expense', '🛒'],
            )
            # Create 3 expense transactions for March 2026
            for i in range(3):
                tx_id = str(uuid.uuid4())
                self._tx_ids.append(tx_id)
                cursor.execute(
                    """INSERT INTO transactions (id, user_id, account_id, category_id, type, amount, currency, date, note)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    [tx_id, self.user_id, self.account_id, self.category_id,
                     'expense', 100 + i * 50, 'EGP', date(2026, 3, 10 + i), f'Test expense {i}'],
                )
            # Add income transaction
            tx_id = str(uuid.uuid4())
            self._tx_ids.append(tx_id)
            cursor.execute(
                """INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, note)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                [tx_id, self.user_id, self.account_id,
                 'income', 5000, 'EGP', date(2026, 3, 1), 'Test income'],
            )

    def tearDown(self):
        """Clean up all test data."""
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM transactions WHERE user_id = %s", [self.user_id])
            cursor.execute("DELETE FROM sessions WHERE user_id = %s", [self.user_id])
            cursor.execute("DELETE FROM accounts WHERE user_id = %s", [self.user_id])
            cursor.execute("DELETE FROM institutions WHERE user_id = %s", [self.user_id])
            cursor.execute("DELETE FROM categories WHERE user_id = %s", [self.user_id])
            cursor.execute("DELETE FROM users WHERE id = %s", [self.user_id])

    def test_reports_returns_200(self):
        """Authenticated request to /reports should return 200."""
        response = self.client.get('/reports', **{
            'HTTP_COOKIE': f'{COOKIE_NAME}={self.session_token}',
        })
        self.assertEqual(response.status_code, 200)

    def test_reports_contains_chart_html(self):
        """Reports page should contain chart-related HTML."""
        response = self.client.get('/reports?year=2026&month=3', **{
            'HTTP_COOKIE': f'{COOKIE_NAME}={self.session_token}',
        })
        content = response.content.decode()
        self.assertIn('Spending by Category', content)
        self.assertIn('Income vs Expenses', content)

    def test_reports_with_currency_filter(self):
        """Reports page should work with currency filter."""
        response = self.client.get('/reports?year=2026&month=3&currency=EGP', **{
            'HTTP_COOKIE': f'{COOKIE_NAME}={self.session_token}',
        })
        self.assertEqual(response.status_code, 200)

    def test_reports_month_navigation(self):
        """Reports page should contain prev/next month links."""
        response = self.client.get('/reports?year=2026&month=3', **{
            'HTTP_COOKIE': f'{COOKIE_NAME}={self.session_token}',
        })
        content = response.content.decode()
        self.assertIn('Prev', content)
        self.assertIn('Next', content)

    def test_reports_empty_month(self):
        """Reports for a month with no data should return 200."""
        response = self.client.get('/reports?year=2020&month=1', **{
            'HTTP_COOKIE': f'{COOKIE_NAME}={self.session_token}',
        })
        self.assertEqual(response.status_code, 200)

    def test_reports_redirects_without_auth(self):
        """Unauthenticated request should redirect to /login."""
        response = self.client.get('/reports')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/login')


class SpendingByCategoryTest(TransactionTestCase):
    """Tests for _get_spending_by_category — SQL aggregation logic."""

    def setUp(self):
        """Create user, account, category, and expense transactions."""
        self.user_id = str(uuid.uuid4())
        self.account_id = str(uuid.uuid4())
        self.category_id = str(uuid.uuid4())
        self.inst_id = str(uuid.uuid4())

        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO users (id, email) VALUES (%s, %s)",
                [self.user_id, f'spend-{uuid.uuid4().hex[:8]}@example.com'],
            )
            cursor.execute(
                "INSERT INTO institutions (id, user_id, name) VALUES (%s, %s, %s)",
                [self.inst_id, self.user_id, 'Test Bank'],
            )
            cursor.execute(
                "INSERT INTO accounts (id, user_id, institution_id, name, type, currency, current_balance) VALUES (%s, %s, %s, %s, 'savings'::account_type, 'EGP'::currency_type, %s)",
                [self.account_id, self.user_id, self.inst_id, 'Test', 0],
            )
            cursor.execute(
                "INSERT INTO categories (id, user_id, name, type, icon) VALUES (%s, %s, %s, %s, %s)",
                [self.category_id, self.user_id, 'Food', 'expense', '🛒'],
            )
            for i in range(3):
                cursor.execute(
                    """INSERT INTO transactions (id, user_id, account_id, category_id, type, amount, currency, date)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    [str(uuid.uuid4()), self.user_id, self.account_id, self.category_id,
                     'expense', 100 + i * 50, 'EGP', date(2026, 3, 10 + i)],
                )

    def tearDown(self):
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM transactions WHERE user_id = %s", [self.user_id])
            cursor.execute("DELETE FROM accounts WHERE user_id = %s", [self.user_id])
            cursor.execute("DELETE FROM institutions WHERE user_id = %s", [self.user_id])
            cursor.execute("DELETE FROM categories WHERE user_id = %s", [self.user_id])
            cursor.execute("DELETE FROM users WHERE id = %s", [self.user_id])

    def test_returns_spending_data(self):
        """Should return spending with correct total for March 2026."""
        spending, total = _get_spending_by_category(self.user_id, 2026, 3)
        self.assertGreater(total, 0)
        self.assertGreater(len(spending), 0)
        self.assertAlmostEqual(total, 450.0, places=2)

    def test_percentages_sum_to_100(self):
        """Category percentages should sum to approximately 100."""
        spending, total = _get_spending_by_category(self.user_id, 2026, 3)
        if spending:
            pct_sum = sum(s['percentage'] for s in spending)
            self.assertAlmostEqual(pct_sum, 100.0, places=1)

    def test_empty_month_returns_no_data(self):
        """A month with no expenses should return empty list."""
        spending, total = _get_spending_by_category(self.user_id, 2020, 1)
        self.assertEqual(spending, [])
        self.assertEqual(total, 0.0)


class MonthSummaryTest(TransactionTestCase):
    """Tests for _get_month_summary — income/expense totals."""

    def setUp(self):
        """Create user, account, and transactions (income + expense)."""
        self.user_id = str(uuid.uuid4())
        self.account_id = str(uuid.uuid4())
        self.inst_id = str(uuid.uuid4())

        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO users (id, email) VALUES (%s, %s)",
                [self.user_id, f'summary-{uuid.uuid4().hex[:8]}@example.com'],
            )
            cursor.execute(
                "INSERT INTO institutions (id, user_id, name) VALUES (%s, %s, %s)",
                [self.inst_id, self.user_id, 'Test Bank'],
            )
            cursor.execute(
                "INSERT INTO accounts (id, user_id, institution_id, name, type, currency, current_balance) VALUES (%s, %s, %s, %s, 'savings'::account_type, 'EGP'::currency_type, %s)",
                [self.account_id, self.user_id, self.inst_id, 'Test', 0],
            )
            # Income
            cursor.execute(
                """INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                [str(uuid.uuid4()), self.user_id, self.account_id, 'income', 5000, 'EGP', date(2026, 3, 1)],
            )
            # Expenses
            for i in range(3):
                cursor.execute(
                    """INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    [str(uuid.uuid4()), self.user_id, self.account_id, 'expense', 100 + i * 50, 'EGP', date(2026, 3, 10 + i)],
                )

    def tearDown(self):
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM transactions WHERE user_id = %s", [self.user_id])
            cursor.execute("DELETE FROM accounts WHERE user_id = %s", [self.user_id])
            cursor.execute("DELETE FROM institutions WHERE user_id = %s", [self.user_id])
            cursor.execute("DELETE FROM users WHERE id = %s", [self.user_id])

    def test_returns_correct_totals(self):
        """Should return correct income and expense totals."""
        summary = _get_month_summary(self.user_id, 2026, 3)
        self.assertEqual(summary['income'], 5000.0)
        self.assertAlmostEqual(summary['expenses'], 450.0, places=2)
        self.assertAlmostEqual(summary['net'], 4550.0, places=2)


class ChartBuildersTest(TestCase):
    """Tests for chart data building functions — no database needed."""

    def test_build_chart_segments_empty(self):
        """Empty spending should return empty segments."""
        self.assertEqual(_build_chart_segments([], 0), [])

    def test_build_chart_segments_assigns_colors(self):
        """Each segment should get a color from the palette."""
        spending = [
            {'name': 'Food', 'amount': 60, 'percentage': 60},
            {'name': 'Transport', 'amount': 40, 'percentage': 40},
        ]
        segments = _build_chart_segments(spending, 100)
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0]['color'], '#0d9488')
        self.assertEqual(segments[1]['color'], '#dc2626')

    def test_build_bar_chart_empty(self):
        """Empty history should return empty groups and legend."""
        groups, legend = _build_bar_chart([])
        self.assertEqual(groups, [])
        self.assertEqual(legend, [])

    def test_build_bar_chart_normalizes_heights(self):
        """The tallest bar should be 100%."""
        history = [
            {'year': 2026, 'month': 1, 'month_name': 'January', 'income': 1000, 'expenses': 500, 'net': 500},
            {'year': 2026, 'month': 2, 'month_name': 'February', 'income': 2000, 'expenses': 800, 'net': 1200},
        ]
        groups, legend = _build_bar_chart(history)
        self.assertEqual(len(groups), 2)
        feb_income_height = groups[1]['bars'][0]['height_pct']
        self.assertAlmostEqual(feb_income_height, 100.0, places=1)
        self.assertEqual(len(legend), 2)
