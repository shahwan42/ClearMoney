"""Transaction detail bottom sheet tests.

Verifies that tapping a transaction row opens a detail bottom sheet
with read-only info, and that Edit/Duplicate/Delete actions work from the sheet.
"""

import sys
import os
import re

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


@pytest.fixture(scope="function", autouse=True)
def db() -> None:
    """Reset DB and create test institution + account."""
    global _account_id, _user_id
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
                " (user_id, institution_id, name, type, currency,"
                " current_balance, initial_balance, display_order)"
                " VALUES (%s, %s, 'Current', 'current', 'EGP', 10000, 10000, 0)"
                " RETURNING id",
                (_user_id, inst_id),
            )
            _account_id = str(cur.fetchone()[0])  # type: ignore[index]
        conn.commit()


@pytest.fixture(autouse=True)
def auth(db: None, page: Page) -> None:
    ensure_auth(page)


def _create_test_transaction(page: Page, amount: str = "250", note: str = "Dinner") -> str:
    """Create a transaction and return the transaction ID."""
    category_id = get_category_id("expense", _user_id)
    create_transaction(page, _account_id, category_id, amount, "expense", note=note)
    page.goto("/transactions")
    # Wait for transaction row to appear
    expect(page.locator("main")).to_contain_text(note)
    return note


def _open_detail_sheet(page: Page) -> None:
    """Click the first transaction row and wait for sheet content to load."""
    page.locator('[role="button"][id^="tx-"]').first.click()
    # Wait for HTMX to load content into the sheet
    page.wait_for_selector("#tx-detail-content h4", timeout=5000)


class TestTransactionDetailSheet:
    """Tapping a transaction row opens a detail bottom sheet."""

    def test_row_click_opens_detail_sheet(self, page: Page) -> None:
        category_id = get_category_id("expense", _user_id)
        create_transaction(
            page, _account_id, category_id, "250", "expense", note="Dinner"
        )
        page.goto("/transactions")
        _open_detail_sheet(page)
        content = page.locator("#tx-detail-content")
        expect(content).to_contain_text("250")
        expect(content).to_contain_text("Dinner")

    def test_detail_sheet_shows_account(self, page: Page) -> None:
        _create_test_transaction(page)
        _open_detail_sheet(page)
        content = page.locator("#tx-detail-content")
        expect(content).to_contain_text("Current")

    def test_edit_button_closes_sheet_opens_edit_form(self, page: Page) -> None:
        _create_test_transaction(page)
        row = page.locator('[role="button"][id^="tx-"]').first
        row.click()
        page.wait_for_selector("#tx-detail-content h4", timeout=5000)
        content = page.locator("#tx-detail-content")
        # Click Edit button — closes detail sheet and opens tx-edit sheet
        content.locator("button:has-text('Edit')").click()
        # Detail sheet should close
        detail_sheet = page.locator("#tx-detail-sheet")
        expect(detail_sheet).to_have_attribute("aria-hidden", "true", timeout=3000)
        # Edit sheet opens with the edit form
        edit_sheet_content = page.locator("#tx-edit-content")
        expect(edit_sheet_content.locator("input[name='amount']")).to_be_visible(
            timeout=5000
        )

    def test_delete_button_removes_row(self, page: Page) -> None:
        category_id = get_category_id("expense", _user_id)
        create_transaction(
            page, _account_id, category_id, "75", "expense", note="ToDelete"
        )
        page.goto("/transactions")
        row = page.locator('[role="button"][id^="tx-"]', has_text="ToDelete").first
        row_id = row.get_attribute("id")
        row.click()
        page.wait_for_selector("#tx-detail-content h4", timeout=5000)
        content = page.locator("#tx-detail-content")
        delete_btn = content.locator("button.tx-delete-btn")
        
        # First click arms the button (two-step delete)
        delete_btn.click()
        expect(delete_btn).to_contain_text("Tap again to confirm delete")
        
        # Second click performs the deletion
        with page.expect_response(lambda r: r.request.method == "DELETE"):
            delete_btn.click()
            
        expect(page.locator(f"#{row_id}")).to_have_count(0, timeout=5000)

    def test_duplicate_transaction(self, page: Page) -> None:
        """Duplicate button opens new transaction form with prefilled data."""
        category_id = get_category_id("expense", _user_id)
        create_transaction(
            page, _account_id, category_id, "50.50", "expense", note="ToDuplicate"
        )
        page.goto("/transactions")
        _open_detail_sheet(page)
        
        # Click Duplicate
        page.locator("#tx-detail-content a:has-text('Duplicate')").click()
        
        # Should be on /transactions/new with prefilled data
        expect(page).to_have_url(re.compile(r"/transactions/new\?dup=.*"))
        expect(page.locator("input[name='amount']")).to_have_value("50.50")
        expect(page.locator("input[name='note']")).to_have_value("ToDuplicate")

    def test_kebab_menu_still_works(self, page: Page) -> None:
        _create_test_transaction(page)
        row = page.locator('[role="button"][id^="tx-"]').first
        kebab = row.locator("[data-kebab-trigger]")
        kebab.click()
        menu = row.locator("[data-kebab-menu]")
        expect(menu).to_be_visible()
        # Sheet should remain closed
        sheet = page.locator("#tx-detail-sheet")
        expect(sheet).to_have_attribute("aria-hidden", "true")

    def test_sheet_has_aria_attributes(self, page: Page) -> None:
        _create_test_transaction(page)
        page.locator('[role="button"][id^="tx-"]').first.click()
        sheet = page.locator("#tx-detail-sheet")
        expect(sheet).to_be_visible()
        expect(sheet).to_have_attribute("role", "dialog")
        expect(sheet).to_have_attribute("aria-modal", "true")
