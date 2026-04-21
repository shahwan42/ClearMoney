"""Health warnings E2E tests — T077.

Tests that account health warnings (min balance, missing deposit) render correctly,
can be dismissed, and stay dismissed across HTMX navigation.
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
    reset_database,
)

_account_id: str = ""
_user_id: str = ""

@pytest.fixture(scope="function", autouse=True)
def db() -> None:
    global _account_id, _user_id
    _user_id = reset_database()
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO institutions (user_id, name, type, display_order)"
                " VALUES (%s, 'Test Bank', 'bank', 0) RETURNING id",
                (_user_id,),
            )
            inst_id = str(cur.fetchone()[0])
            # Create an account with a min_balance constraint in health_config
            cur.execute(
                "INSERT INTO accounts"
                " (user_id, institution_id, name, type, currency, current_balance, initial_balance, display_order, health_config)"
                " VALUES (%s, %s, 'Savings', 'savings', 'EGP', 500, 500, 0, '{\"min_balance\": 1000}') RETURNING id",
                (_user_id, inst_id),
            )
            _account_id = str(cur.fetchone()[0])
        conn.commit()

@pytest.fixture(autouse=True)
def auth(db: None, page: Page) -> None:
    ensure_auth(page)

class TestHealthWarnings:
    def test_health_warning_visible_when_below_min_balance(self, page: Page) -> None:
        """Dashboard shows health warning when account balance is below minimum."""
        page.goto("/")
        # Warning should be visible (Savings 500 < 1000 min)
        warning = page.locator("[data-health-tag*='min_balance']")
        expect(warning).to_be_visible()
        expect(warning).to_contain_text("balance (500.00) is below minimum (1,000.00)")

    def test_dismiss_health_warning(self, page: Page) -> None:
        """Dismissing a health warning removes it from the page and localStorage."""
        page.goto("/")
        warning = page.locator("[data-health-tag*='min_balance']")
        expect(warning).to_be_visible()

        # Click dismiss button
        page.evaluate("document.querySelector('button[aria-label=\"Dismiss warning\"]').click()")
        expect(warning).not_to_be_visible()

        # Verify it stays hidden on reload
        page.reload()
        expect(page.locator("[data-health-tag*='min_balance']")).not_to_be_visible()

    def test_health_warning_stays_dismissed_across_htmx_navigation(self, page: Page) -> None:
        """Health warning remains hidden after dismissing and navigating via HTMX."""
        page.goto("/")
        warning = page.locator("[data-health-tag*='min_balance']")
        expect(warning).to_be_visible()

        # Dismiss it
        tag = warning.get_attribute("data-health-tag")
        page.evaluate("document.querySelector('button[aria-label=\"Dismiss warning\"]').click()")
        expect(warning).not_to_be_visible()

        # Navigate to another page (Accounts) via HTMX (hx-boost)
        page.click("nav a:has-text('Accounts')")
        expect(page).to_have_url("/accounts")

        # Navigate back to Dashboard via HTMX
        page.click("nav a:has-text('Home')")
        expect(page).to_have_url("/")

        # Warning should NOT reappear (flicker check)
        expect(page.locator(f"[data-health-tag='{tag}']")).not_to_be_visible()
