"""Recurring transaction rule tests.

UI notes:
- Form lives in a bottom sheet opened by the "+ Automation" button
- Account: combobox (#rec-account-combobox with ._accountCombobox.selectById)
- Category: combobox (#rec-category-combobox with ._combobox.selectById)
- Submit button text: "Create Rule" (new) / "Save Changes" (edit)
- Auto-confirm: toggle button #rec-auto-confirm-toggle (aria-checked)
- Destination account container: #rec-dest-account-container
- Category container: #rec-category-container
- Fee: #rec-fee-input (inside #rec-more-options, collapsed by default)
- Success renders in #rec-form-result; "Done" closes sheet; "Add another" reloads form in sheet
- Delete button: text "Del", hx-delete, hx-confirm fires custom dialog
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from playwright.sync_api import Page, expect
from conftest import (
    _conn,
    ensure_auth,
    get_category_id,
    reset_database,
)

_account_id: str = ""
_account_id_2: str = ""
_user_id: str = ""


@pytest.fixture(scope="function", autouse=True)
def db() -> None:
    """Reset DB and create test institution + two accounts directly via SQL."""
    global _account_id, _account_id_2, _user_id
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
            cur.execute(
                "INSERT INTO accounts"
                " (user_id, institution_id, name, type, currency, current_balance, initial_balance, display_order)"
                " VALUES (%s, %s, 'Savings', 'savings', 'EGP', 5000, 5000, 1) RETURNING id",
                (_user_id, inst_id),
            )
            _account_id_2 = str(cur.fetchone()[0])  # type: ignore[index]
        conn.commit()


@pytest.fixture(autouse=True)
def auth(db: None, page: Page) -> None:
    ensure_auth(page)


def _open_new_form(page: Page) -> None:
    """Open the new automation bottom sheet and wait for form to load."""
    page.goto("/recurring")
    page.click('button:has-text("+ Automation")')
    page.wait_for_selector("#rec-form", timeout=5000)


def _create_recurring_rule(page: Page, note: str = "Netflix", amount: str = "200", frequency: str = "monthly") -> None:
    """Create a recurring rule via the UI using the bottom sheet form."""
    category_id = get_category_id("expense", _user_id)
    _open_new_form(page)
    page.fill("#rec-amount", amount)
    page.evaluate(
        f"document.getElementById('rec-account-combobox')._accountCombobox.selectById('{_account_id}')"
    )
    page.evaluate(
        f"document.getElementById('rec-category-combobox')._combobox.selectById('{category_id}')"
    )
    page.fill("#rec-note-input", note)
    page.select_option("#rec-frequency", frequency)
    page.fill("#rec-next-due", "2026-04-01")
    with page.expect_response(
        lambda r: "/recurring/add" in r.url and r.request.method == "POST"
    ):
        page.click('button:has-text("Create Rule")')


class TestRecurring:
    def test_create_recurring_rule(self, page: Page) -> None:
        category_id = get_category_id("expense", _user_id)
        _open_new_form(page)
        page.fill("#rec-amount", "200")
        page.evaluate(
            f"document.getElementById('rec-account-combobox')._accountCombobox.selectById('{_account_id}')"
        )
        page.evaluate(
            f"document.getElementById('rec-category-combobox')._combobox.selectById('{category_id}')"
        )
        page.fill("#rec-note-input", "Netflix")
        page.select_option("#rec-frequency", "monthly")
        page.fill("#rec-next-due", "2026-04-01")
        with page.expect_response(
            lambda r: "/recurring/add" in r.url and r.request.method == "POST"
        ):
            page.click('button:has-text("Create Rule")')
        expect(page.locator("#recurring-list")).to_contain_text("Netflix")

    def test_recurring_list_shows_frequency(self, page: Page) -> None:
        _create_recurring_rule(page)
        expect(page.locator("#recurring-list")).to_contain_text("Netflix")
        expect(page.locator("#recurring-list")).to_contain_text("monthly")

    def test_create_shows_success_message(self, page: Page) -> None:
        """After creation, success panel shows rule summary inside the sheet."""
        _create_recurring_rule(page, note="Vodafone bill", amount="500")
        success = page.locator("#rec-form-result")
        expect(success).to_contain_text("Rule created")
        expect(success).to_contain_text("Vodafone bill")
        expect(success).to_contain_text("monthly")
        expect(success).to_contain_text("Next reminder")
        # OOB list refresh shows new rule
        expect(page.locator("#recurring-list")).to_contain_text("Vodafone bill")

    def test_add_another_keeps_sticky_values(self, page: Page) -> None:
        """'Add another' reloads form with account + frequency sticky values."""
        category_id = get_category_id("expense", _user_id)
        _open_new_form(page)
        page.fill("#rec-amount", "300")
        page.evaluate(
            f"document.getElementById('rec-account-combobox')._accountCombobox.selectById('{_account_id_2}')"
        )
        page.evaluate(
            f"document.getElementById('rec-category-combobox')._combobox.selectById('{category_id}')"
        )
        page.fill("#rec-note-input", "Internet")
        page.select_option("#rec-frequency", "quarterly")
        page.fill("#rec-next-due", "2026-04-01")
        # Turn on auto-confirm toggle
        page.click("#rec-auto-confirm-toggle")
        expect(page.locator("#rec-auto-confirm-toggle")).to_have_attribute("aria-checked", "true")
        with page.expect_response(
            lambda r: "/recurring/add" in r.url and r.request.method == "POST"
        ):
            page.click('button:has-text("Create Rule")')
        # Click "Add another" — reloads form in sheet
        with page.expect_response(
            lambda r: "/recurring/form" in r.url and r.request.method == "GET"
        ):
            page.click('button:has-text("Add another")')
        # Sticky: frequency preserved
        expect(page.locator("#rec-frequency")).to_have_value("quarterly")
        # Sticky: auto_confirm toggle is on
        expect(page.locator("#rec-auto-confirm-toggle")).to_have_attribute("aria-checked", "true")
        # Reset fields blank
        expect(page.locator("#rec-amount")).to_have_value("")
        expect(page.locator("#rec-note-input")).to_have_value("")

    def test_done_closes_sheet(self, page: Page) -> None:
        """'Done' button closes the bottom sheet."""
        _create_recurring_rule(page, note="One-off", amount="100")
        page.click('button:has-text("Done")')
        # Overlay should not be visible after sheet closes
        expect(page.locator("#new-automation-sheet-overlay")).not_to_be_visible()

    def test_delete_recurring_rule(self, page: Page) -> None:
        _create_recurring_rule(page)
        # Navigate fresh so sheet is closed and list is interactive
        page.goto("/recurring")
        # Verify rule exists before deleting
        expect(page.locator("#recurring-list")).to_contain_text("Netflix")
        # Click Del — hx-ext="confirm-dialog" shows a custom branded dialog (not browser confirm)
        page.click('button:has-text("Del")')
        # Wait for custom confirm dialog and click the confirm button
        expect(page.locator("#confirm-dialog-confirm")).to_be_visible(timeout=5000)
        with page.expect_response(
            lambda r: "/recurring/" in r.url and r.request.method == "DELETE"
        ):
            page.click("#confirm-dialog-confirm")
        expect(page.locator("#recurring-list")).not_to_contain_text("Netflix")


class TestRecurringTransfer:
    def test_create_transfer_rule(self, page: Page) -> None:
        """Create a transfer recurring rule with fee via UI."""
        _open_new_form(page)
        # Select "Transfer" type
        page.click('input[name="type"][value="transfer"]', force=True)
        # Destination account container should be visible
        expect(page.locator("#rec-dest-account-container")).to_be_visible()
        # Category should be hidden
        expect(page.locator("#rec-category-container")).to_be_hidden()
        # Fill form
        page.fill("#rec-amount", "1000")
        page.evaluate(
            f"document.getElementById('rec-account-combobox')._accountCombobox.selectById('{_account_id}')"
        )
        page.select_option('select[name="counter_account_id"]', _account_id_2)
        # Open More options to fill fee
        page.click('#rec-more-options-toggle')
        expect(page.locator("#rec-more-options")).to_be_visible()
        page.fill('input[name="fee_amount"]', "10")
        page.fill("#rec-note-input", "Monthly rent")
        page.select_option("#rec-frequency", "monthly")
        page.fill("#rec-next-due", "2026-04-01")
        with page.expect_response(
            lambda r: "/recurring/add" in r.url and r.request.method == "POST"
        ):
            page.click('button:has-text("Create Rule")')
        expect(page.locator("#recurring-list")).to_contain_text("Monthly rent")
        # Verify transfer-specific display
        expect(page.locator("#recurring-list")).to_contain_text("→")

    def test_transfer_toggle_shows_hides_fields(self, page: Page) -> None:
        """Toggling between types shows/hides destination account and category."""
        _open_new_form(page)
        # Initially expense — no dest account, category visible
        expect(page.locator("#rec-dest-account-container")).to_be_hidden()
        expect(page.locator("#rec-category-container")).to_be_visible()
        # Switch to transfer
        page.click('input[name="type"][value="transfer"]', force=True)
        expect(page.locator("#rec-dest-account-container")).to_be_visible()
        expect(page.locator("#rec-category-container")).to_be_hidden()
        # Switch back to expense
        page.click('input[name="type"][value="expense"]', force=True)
        expect(page.locator("#rec-dest-account-container")).to_be_hidden()
        expect(page.locator("#rec-category-container")).to_be_visible()
