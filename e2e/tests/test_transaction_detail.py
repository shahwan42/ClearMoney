"""Transaction detail bottom sheet tests.

Verifies that tapping a transaction row opens a detail bottom sheet
with read-only info, and that Edit/Delete actions work from the sheet.
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


def _open_detail_sheet(page: Page) -> None:
    """Click the first transaction row and wait for sheet content to load."""
    page.locator('[role="button"][id^="tx-"]').first.click()
    # Wait for HTMX to load content into the sheet
    page.wait_for_selector("#tx-detail-content dl", timeout=5000)


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
        page.goto("/transactions")
        _open_detail_sheet(page)
        content = page.locator("#tx-detail-content")
        expect(content).to_contain_text("Current")

    def test_edit_button_closes_sheet_opens_edit_form(self, page: Page) -> None:
        page.goto("/transactions")
        row = page.locator('[role="button"][id^="tx-"]').first
        row.click()
        page.wait_for_selector("#tx-detail-content dl", timeout=5000)
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
        page.wait_for_selector("#tx-detail-content dl", timeout=5000)
        content = page.locator("#tx-detail-content")
        page.on("dialog", lambda d: d.accept())
        content.locator("button:has-text('Delete')").click()
        expect(page.locator(f"#{row_id}")).to_have_count(0, timeout=5000)

    def test_kebab_menu_still_works(self, page: Page) -> None:
        page.goto("/transactions")
        row = page.locator('[role="button"][id^="tx-"]').first
        kebab = row.locator("[data-kebab-trigger]")
        kebab.click()
        menu = row.locator("[data-kebab-menu]")
        expect(menu).to_be_visible()
        # Sheet should remain closed
        sheet = page.locator("#tx-detail-sheet")
        expect(sheet).to_have_attribute("aria-hidden", "true")

    def test_sheet_has_aria_attributes(self, page: Page) -> None:
        page.goto("/transactions")
        page.locator('[role="button"][id^="tx-"]').first.click()
        sheet = page.locator("#tx-detail-sheet")
        expect(sheet).to_be_visible()
        expect(sheet).to_have_attribute("role", "dialog")
        expect(sheet).to_have_attribute("aria-modal", "true")
