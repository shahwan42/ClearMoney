"""Monthly budget tests.

Converts: 15-budgets.spec.ts

UI notes:
- Create form: regular POST on /budgets, button text "Create Budget"
- Category select: first option is empty, then expense and income categories
- Delete: regular POST form with button text "Delete", action="/budgets/{id}/delete"
- Progress bar: .bg-gray-100.rounded-full.h-2.5
- Remaining text: "X remaining" or "Over budget by X"
- Empty state: "No budgets set. Create one above!"
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from playwright.sync_api import Page, expect
from conftest import (
    _conn,
    create_transaction,
    ensure_auth,
    get_category_id,
    reset_database,
)

_account_id: str = ""
_user_id: str = ""
_category_id: str = ""


def _create_budget(page: Page, category_id: str, limit: str = "2000") -> None:
    """Create a budget via the UI."""
    page.goto("/budgets")
    # Category uses a custom combobox — select via its programmatic API
    page.evaluate(
        f"document.querySelector('[data-category-combobox]')._combobox.selectById('{category_id}')"
    )
    # Use the budget form's specific input ID (page has two monthly_limit inputs)
    page.fill('input#cat-monthly-limit', limit)
    with page.expect_response(
        lambda r: "/budgets" in r.url and r.request.method == "POST"
    ):
        page.locator('button:has-text("Create Budget")').click()


@pytest.fixture(scope="function", autouse=True)
def db() -> None:
    """Reset DB and create test institution + account directly via SQL."""
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
                " VALUES (%s, %s, 'Current', 'current', 'EGP', 10000, 10000, 0) RETURNING id",
                (_user_id, inst_id),
            )
            _account_id = str(cur.fetchone()[0])  # type: ignore[index]
        conn.commit()
    _category_id = get_category_id("expense", _user_id)


@pytest.fixture(autouse=True)
def auth(db: None, page: Page) -> None:
    ensure_auth(page)


class TestBudgets:
    def test_create_budget(self, page: Page) -> None:
        _create_budget(page, _category_id)
        expect(page.locator("main")).to_contain_text("2,000")

    def test_budget_progress_bar_visible(self, page: Page) -> None:
        _create_budget(page, _category_id)
        expect(page.locator(".bg-gray-100.rounded-full")).to_be_visible()

    def test_budget_shows_remaining_amount(self, page: Page) -> None:
        _create_budget(page, _category_id)
        create_transaction(page, _account_id, _category_id, "500", "expense")
        page.goto("/budgets")
        expect(page.locator("main")).to_contain_text("remaining")

    def test_update_budget_limit(self, page: Page) -> None:
        _create_budget(page, _category_id, "2000")
        page.goto("/budgets")
        # The inline edit input shows current value
        edit_input = page.locator('input[name="monthly_limit"][value="2000.00"]')
        expect(edit_input).to_be_visible()
        edit_input.fill("3500")
        # Click the Update button on the budget card (not the total budget one)
        edit_input.locator("..").locator('button:has-text("Update")').click()
        page.wait_for_load_state()
        expect(page.locator("main")).to_contain_text("3,500")

    def test_budget_detail_shows_transactions(self, page: Page) -> None:
        _create_budget(page, _category_id, "5000")
        create_transaction(page, _account_id, _category_id, "750", "expense")
        page.goto("/budgets")
        # Click the budget spending area (the link wrapping the progress bar)
        page.locator('a[href*="/budgets/"]').first.click()
        page.wait_for_load_state()
        # Should show budget detail with the transaction
        expect(page.locator("main")).to_contain_text("Transactions this month")
        expect(page.locator("main")).to_contain_text("750")

    def test_budget_detail_back_navigation(self, page: Page) -> None:
        _create_budget(page, _category_id, "5000")
        page.goto("/budgets")
        page.locator('a[href*="/budgets/"]').first.click()
        page.wait_for_load_state()
        # Click back link
        page.locator('a[aria-label="Back to budgets"]').click()
        page.wait_for_load_state()
        expect(page).to_have_url("/budgets")

    def test_delete_budget(self, page: Page) -> None:
        _create_budget(page, _category_id)
        page.goto("/budgets")
        # Use text selector — the create form says "Create Budget", delete says "Delete"
        page.click('button:has-text("Delete")')
        page.wait_for_load_state()
        expect(page.locator("main")).not_to_contain_text("2,000")
