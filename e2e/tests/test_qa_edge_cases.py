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
        """Budget monthly limit input must have min=0.01 to prevent zero limits."""
        page.goto("/budgets")

        # The "New Budget" section is always visible on the page (not behind a button)
        limit_input = page.locator("input[name='monthly_limit']").first

        # Verify the min constraint prevents zero/negative amounts
        expect(limit_input).to_have_attribute("min", "0.01")

    def test_huge_note_in_quick_entry(self, page: Page) -> None:
        """Note input in Quick-Entry enforces maxlength, truncating overlong input."""
        # Quick entry is a bottom-sheet partial; load it directly
        page.goto("/transactions/quick-form")

        note_input = page.locator("input[name='note']")
        max_length_attr = note_input.get_attribute("maxlength")
        assert max_length_attr is not None, "note input must have a maxlength attribute"

        max_length = int(max_length_attr)
        huge_note = "A" * (max_length + 50)
        note_input.fill(huge_note)

        val = note_input.input_value()
        assert len(val) == max_length, f"Expected {max_length} chars, got {len(val)}"
