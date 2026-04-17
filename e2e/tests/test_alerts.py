"""Smart alerts / push notifications E2E tests — T071.

Tests that budget-threshold conditions generate the correct in-app notifications
via GET /api/push/check, and that the notification banner renders on page load.
"""
import sys
import os
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from playwright.sync_api import Page, expect
from conftest import (
    _conn,
    ensure_auth,
    get_category_id,
    reset_database,
    create_transaction,
)

_account_id: str = ""
_user_id: str = ""
_category_id: str = ""


@pytest.fixture(scope="function", autouse=True)
def db() -> None:
    global _account_id, _user_id, _category_id
    _user_id = reset_database()
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO institutions (user_id, name, type, display_order)"
                " VALUES (%s, 'Test Bank', 'bank', 0) RETURNING id",
                (_user_id,),
            )
            inst_id = str(cur.fetchone()[0])  # type: ignore[index]
            cur.execute(
                "INSERT INTO accounts"
                " (user_id, institution_id, name, type, currency, current_balance, initial_balance, display_order)"
                " VALUES (%s, %s, 'Current', 'current', 'EGP', 50000, 50000, 0) RETURNING id",
                (_user_id, inst_id),
            )
            _account_id = str(cur.fetchone()[0])  # type: ignore[index]

            cur.execute(
                "SELECT id FROM categories WHERE user_id = %s AND type = 'expense' LIMIT 1",
                (_user_id,),
            )
            cat_row = cur.fetchone()
            assert cat_row is not None
            _category_id = str(cat_row[0])
        conn.commit()


@pytest.fixture(autouse=True)
def auth(db: None, page: Page) -> None:
    ensure_auth(page)


def _create_budget(monthly_limit: int) -> str:
    """Insert a budget via SQL and return its ID."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO budgets (user_id, category_id, monthly_limit, currency, rollover_enabled)"
                " VALUES (%s, %s, %s, 'EGP', false) RETURNING id",
                (_user_id, _category_id, monthly_limit),
            )
            row = cur.fetchone()
            assert row is not None
            budget_id = str(row[0])
        conn.commit()
    return budget_id


class TestSmartAlerts:
    def test_push_check_returns_empty_with_no_budgets(self, page: Page) -> None:
        """GET /api/push/check returns an empty list when no conditions are met."""
        resp = page.request.get("/api/push/check")
        assert resp.ok
        data = resp.json()
        assert isinstance(data, list)
        # No budgets created → no budget notifications
        budget_notifs = [n for n in data if "budget" in n.get("tag", "").lower()]
        assert len(budget_notifs) == 0

    def test_push_check_returns_budget_warning_at_80_percent(
        self, page: Page
    ) -> None:
        """Budget at 80%+ spending triggers a warning notification."""
        _create_budget(monthly_limit=1000)
        # Spend 850 EGP (85% → exceeds 80% threshold)
        create_transaction(page, _account_id, _category_id, "850", "expense")
        resp = page.request.get("/api/push/check")
        assert resp.ok
        notifications = resp.json()
        assert isinstance(notifications, list)
        budget_notifs = [
            n for n in notifications
            if "budget-warning" in n.get("tag", "") or "budget-exceeded" in n.get("tag", "")
        ]
        assert len(budget_notifs) >= 1, (
            f"Expected a budget notification but got: {notifications}"
        )

    def test_push_check_returns_budget_exceeded_at_100_percent(
        self, page: Page
    ) -> None:
        """Budget at 100%+ spending triggers an exceeded notification."""
        _create_budget(monthly_limit=500)
        # Spend 600 EGP (120% → exceeds 100%)
        create_transaction(page, _account_id, _category_id, "600", "expense")
        resp = page.request.get("/api/push/check")
        assert resp.ok
        notifications = resp.json()
        budget_notifs = [
            n for n in notifications
            if "budget-exceeded" in n.get("tag", "")
        ]
        assert len(budget_notifs) >= 1, (
            f"Expected budget-exceeded notification but got: {notifications}"
        )

    def test_budget_notification_has_required_fields(self, page: Page) -> None:
        """Budget notification includes title, body, url, and tag fields."""
        _create_budget(monthly_limit=200)
        create_transaction(page, _account_id, _category_id, "180", "expense")
        resp = page.request.get("/api/push/check")
        assert resp.ok
        notifications = resp.json()
        budget_notifs = [
            n for n in notifications
            if "budget" in n.get("tag", "")
        ]
        assert len(budget_notifs) >= 1
        notif = budget_notifs[0]
        assert "title" in notif, "Notification missing 'title' field"
        assert "body" in notif, "Notification missing 'body' field"
        assert "url" in notif, "Notification missing 'url' field"
        assert "tag" in notif, "Notification missing 'tag' field"
        assert notif["url"] == "/budgets", f"Expected url='/budgets', got: {notif['url']}"

    def test_notification_banner_renders_on_page_load(self, page: Page) -> None:
        """In-app notification banner container exists in the DOM on page load."""
        page.goto("/")
        # The push.js injects notifications into #notification-banner
        banner = page.locator("#notification-banner")
        expect(banner).to_be_attached()

    def test_no_notification_below_threshold(self, page: Page) -> None:
        """Budget at 50% spending does NOT trigger a warning."""
        _create_budget(monthly_limit=1000)
        # Spend 500 EGP (50% → below 80% threshold)
        create_transaction(page, _account_id, _category_id, "500", "expense")
        resp = page.request.get("/api/push/check")
        assert resp.ok
        notifications = resp.json()
        budget_notifs = [
            n for n in notifications
            if "budget" in n.get("tag", "")
        ]
        assert len(budget_notifs) == 0, (
            f"Unexpected budget notification at 50%: {notifications}"
        )
