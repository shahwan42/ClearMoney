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


def _open_quick_entry(page: Page) -> None:
    """Open the quick-entry bottom sheet and wait for the form to load."""
    page.goto("/", wait_until="domcontentloaded")
    page.click("button.fab-button", timeout=10000)
    # Wait for the HTMX-loaded form content inside the sheet
    page.wait_for_selector("#qe-amount", timeout=10000)


def _fill_quick_entry(
    page: Page,
    *,
    tx_type: str = "expense",
    amount: str,
    note: str = "",
) -> None:
    """Fill in the quick-entry form fields."""
    # Select transaction type via radio button label click
    page.click(f"input[name='type'][value='{tx_type}']", force=True)

    # Fill amount
    page.fill("#qe-amount", amount)

    # Select the first real account option (index 0 is placeholder "Select account...")
    page.locator("#qe-account-select").select_option(index=1)

    # Category — use the combobox JS API
    category_type = "income" if tx_type == "income" else "expense"
    category_id = get_category_id(category_type, _user_id)
    page.evaluate(
        f"document.getElementById('qe-category-combobox')._combobox.selectById('{category_id}')"
    )

    # Note
    if note:
        page.fill("#qe-note-input", note)


class TestQuickEntry:
    def test_quick_entry_form_loads_immediately(self, page: Page) -> None:
        """Quick-entry sheet: form is visible immediately on open (no empty state)."""
        seed_basic_data(page)
        page.goto("/", wait_until="domcontentloaded")

        # Click FAB to open quick-entry sheet
        page.click("button.fab-button", timeout=10000)

        # Form should be immediately visible (no need to tap Transaction tab)
        # Wait for the sheet to be visible and check for form elements
        page.wait_for_selector("#quick-entry-sheet:not(.hidden)", timeout=5000)
        expect(page.locator("#qe-amount")).to_be_visible(timeout=5000)

        # Verify Transaction tab is visually selected (active styles)
        tab_transaction = page.locator("#tab-transaction")
        expect(tab_transaction).to_have_class(
            "flex-1 py-3 text-sm font-medium text-center rounded-lg border bg-teal-50 text-teal-700 border-teal-200"
        )

    def test_quick_entry_form_resets_on_close(self, page: Page) -> None:
        """Quick-entry sheet: form resets when closed and reopened."""
        seed_basic_data(page)
        page.goto("/", wait_until="domcontentloaded")

        # Open sheet
        page.click("button.fab-button", timeout=10000)
        page.wait_for_selector("#qe-amount", timeout=5000)

        # Fill in some data
        page.fill("#qe-amount", "999")
        page.fill("#qe-note-input", "Test note")

        # Close sheet
        page.click("#quick-entry-overlay")
        page.wait_for_timeout(500)  # Wait for close animation

        # Reopen sheet
        page.click("button.fab-button", timeout=10000)
        page.wait_for_selector("#qe-amount", timeout=5000)

        # Form should be reset (amount field empty)
        expect(page.locator("#qe-amount")).to_have_value("")

    def test_quick_entry_expense_updates_balance(self, page: Page) -> None:
        """Quick-entry expense: form submit -> success message -> dashboard balance decreases."""
        global _user_id
        seed_basic_data(page)
        _open_quick_entry(page)

        # Verify initial balance on dashboard
        expect(page.locator("#dashboard-net-worth")).to_contain_text("10,000")

        _fill_quick_entry(page, tx_type="expense", amount="500", note="Lunch")

        # Submit form (HTMX)
        page.click("#quick-entry-form button[type='submit']")

        # Verify success message
        expect(page.locator("#quick-entry-result")).to_contain_text(
            "Transaction saved!", timeout=10000
        )

        # Navigate to dashboard to verify updated balance
        page.goto("/", wait_until="domcontentloaded")
        expect(page.locator("#dashboard-net-worth")).to_contain_text("9,500")

    def test_quick_entry_income_updates_balance(self, page: Page) -> None:
        """Quick-entry income: form submit -> success message -> dashboard balance increases."""
        seed_basic_data(page)
        _open_quick_entry(page)

        # Verify initial balance
        expect(page.locator("#dashboard-net-worth")).to_contain_text("10,000")

        _fill_quick_entry(page, tx_type="income", amount="2000", note="Bonus")

        # Submit form (HTMX)
        page.click("#quick-entry-form button[type='submit']")

        # Verify success message
        expect(page.locator("#quick-entry-result")).to_contain_text(
            "Transaction saved!", timeout=10000
        )

        # Navigate to dashboard to verify updated balance
        page.goto("/", wait_until="domcontentloaded")
        expect(page.locator("#dashboard-net-worth")).to_contain_text("12,000")

    def test_quick_entry_zero_amount_rejected(self, page: Page) -> None:
        """Quick-entry with zero amount: HTML5 validation prevents submit (min=0.01)."""
        seed_basic_data(page)
        _open_quick_entry(page)

        # Verify initial balance
        expect(page.locator("#dashboard-net-worth")).to_contain_text("10,000")

        # The amount field has min="0.01", so filling "0" and submitting
        # should be blocked by HTML5 validation — the form should not submit.
        page.fill("#qe-amount", "0")

        # Click submit — HTML5 validation should block it
        page.click("#quick-entry-form button[type='submit']")

        # The result area should remain empty (form didn't submit)
        page.wait_for_timeout(500)
        expect(page.locator("#quick-entry-result")).to_be_empty()

        # Balance unchanged
        expect(page.locator("#dashboard-net-worth")).to_contain_text("10,000")
