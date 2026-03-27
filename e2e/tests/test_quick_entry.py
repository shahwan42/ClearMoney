"""Quick-entry transaction form tests.

Verifies that submitting quick-entry transactions updates dashboard balances
via lazy-load OOB swaps.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from playwright.sync_api import Page, expect

from conftest import (
    ensure_auth,
    get_category_id,
    reset_database,
    seed_basic_data,
)

_user_id: str = ""
_institution_id: str = ""
_account_id: str = ""


@pytest.fixture(scope="function", autouse=True)
def db() -> None:
    global _user_id
    _user_id = reset_database()


@pytest.fixture(autouse=True)
def auth(db: None, page: Page) -> None:
    ensure_auth(page)


@pytest.fixture(autouse=True)
def basic_data(auth: None, page: Page) -> None:
    global _institution_id, _account_id
    _institution_id, _account_id = seed_basic_data(page)


class TestQuickEntry:
    def test_quick_entry_expense_updates_balance(self, page: Page) -> None:
        """Quick-entry expense: form submit → success message → dashboard balance decreases."""
        page.goto("/")

        # Get initial balance from dashboard
        net_worth_before = page.locator("#dashboard-net-worth").text_content()
        expect(net_worth_before).to_contain("10,000")

        # Open quick-entry sheet
        page.click("button:has-text('Add')")
        page.wait_for_selector("#quick-entry-sheet", timeout=3000)

        # Fill in quick-entry form
        expense_category_id = get_category_id("expense", _user_id)
        page.select_option('select[name="type"]', "expense")
        page.fill('input[name="amount"]', "500")
        page.select_option('select[name="category_id"]', expense_category_id)
        page.fill('input[name="note"]', "Lunch")

        # Submit form (HTMX)
        page.click("button:has-text('Add Transaction')")

        # Verify success message
        expect(page.locator("#result")).to_contain_text("saved")

        # Wait for dashboard to update via lazy-load OOB
        page.wait_for_timeout(1500)

        # Verify balance decreased by 500
        net_worth_after = page.locator("#dashboard-net-worth").text_content()
        expect(net_worth_after).to_contain("9,500")

    def test_quick_entry_income_updates_balance(self, page: Page) -> None:
        """Quick-entry income: form submit → success message → dashboard balance increases."""
        page.goto("/")

        # Get initial balance from dashboard
        net_worth_before = page.locator("#dashboard-net-worth").text_content()
        expect(net_worth_before).to_contain("10,000")

        # Open quick-entry sheet
        page.click("button:has-text('Add')")
        page.wait_for_selector("#quick-entry-sheet", timeout=3000)

        # Fill in quick-entry form for income
        income_category_id = get_category_id("income", _user_id)
        page.select_option('select[name="type"]', "income")
        page.fill('input[name="amount"]', "2000")
        page.select_option('select[name="category_id"]', income_category_id)
        page.fill('input[name="note"]', "Bonus")

        # Submit form (HTMX)
        page.click("button:has-text('Add Transaction')")

        # Verify success message
        expect(page.locator("#result")).to_contain_text("saved")

        # Wait for dashboard to update via lazy-load OOB
        page.wait_for_timeout(1500)

        # Verify balance increased by 2000
        net_worth_after = page.locator("#dashboard-net-worth").text_content()
        expect(net_worth_after).to_contain("12,000")

    def test_quick_entry_zero_amount_rejected(self, page: Page) -> None:
        """Quick-entry with zero amount: validation error shown, no balance change."""
        page.goto("/")

        # Get initial balance from dashboard
        net_worth_before = page.locator("#dashboard-net-worth").text_content()
        expect(net_worth_before).to_contain("10,000")

        # Open quick-entry sheet
        page.click("button:has-text('Add')")
        page.wait_for_selector("#quick-entry-sheet", timeout=3000)

        # Fill in quick-entry form with zero amount
        expense_category_id = get_category_id("expense", _user_id)
        page.select_option('select[name="type"]', "expense")
        page.fill('input[name="amount"]', "0")
        page.select_option('select[name="category_id"]', expense_category_id)

        # Submit form (HTMX)
        page.click("button:has-text('Add Transaction')")

        # Verify error message (validation error)
        expect(page.locator("#result")).to_contain_text("error")

        # Verify balance unchanged
        page.wait_for_timeout(500)
        net_worth_after = page.locator("#dashboard-net-worth").text_content()
        expect(net_worth_after).to_contain("10,000")
