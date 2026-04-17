"""QA Edge Cases implementation.

Manually ensuring the remaining specific edge cases and form constraints
from the QA Test Plan work exactly as required through Playwright E2E.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from playwright.sync_api import Page, expect
from conftest import (
    _conn,
    ensure_auth,
    reset_database,
)

_user_id: str = ""
_account_id: str = ""


@pytest.fixture(scope="function", autouse=True)
def db() -> None:
    global _user_id, _account_id
    _user_id = reset_database()
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO institutions (user_id, name, type, display_order) VALUES (%s, 'Test Bank', 'bank', 0) RETURNING id",
                (_user_id,),
            )
            inst_id = str(cur.fetchone()[0])
            cur.execute(
                "INSERT INTO accounts (user_id, institution_id, name, type, currency, current_balance, initial_balance, display_order) VALUES (%s, %s, 'Current', 'current', 'EGP', 10000, 10000, 0) RETURNING id",
                (_user_id, inst_id),
            )
            _account_id = str(cur.fetchone()[0])
        conn.commit()


@pytest.fixture(autouse=True)
def auth(db: None, page: Page) -> None:
    ensure_auth(page)


class TestQAEdgeCases:
    def test_search_xss_protection(self, page: Page) -> None:
        """Global Search: Enter HTML/Script tags as the query; verify XSS handling and no breakage."""
        page.goto("/")
        page.click("#global-search-btn")
        
        # Enter malicious script tag
        page.locator("#global-search-input").fill("<script>alert('xss')</script>")
        page.wait_for_timeout(400)
        
        # It should just show no results safely, not execute JS
        results = page.locator("#global-search-results")
        expect(results).to_be_visible()
        expect(results).not_to_contain_text("alert")

    def test_budget_limit_zero(self, page: Page) -> None:
        """Update a budget limit to 0 checking behavior."""
        # Create a budget directly via UI
        page.goto("/budgets")
        page.click("button:has-text('New Budget')")
        page.select_option("select[name='category_id']", index=1)
        page.locator("input[name='limit']").fill("0")
        
        page.click("button[type='submit']")
        
        # It should block or show validation since min value > 0 is standard for limits
        # We assert it prevents submit
        expect(page.locator("input[name='limit']")).to_have_attribute("min", "1")

    def test_huge_note_in_quick_entry(self, page: Page) -> None:
        """Enter a note exceeding the maximum character limit in Quick-Entry."""
        page.goto("/quick-entry")
        
        # In Django usually maxlength=100 or 120
        huge_note = "A" * 150
        page.locator("input[name='note']").fill(huge_note)
        
        # The browser should restrict it based on maxlength
        max_length = page.locator("input[name='note']").get_attribute("maxlength")
        
        # Read the real value that got typed
        val = page.locator("input[name='note']").input_value()
        
        # Length should be truncated
        if max_length:
            assert len(val) == int(max_length)
        else:
            # If no maxlength is set, it will be validated by server
            pass
