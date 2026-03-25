"""Institution and account CRUD tests.

Converts: 02-accounts.spec.ts

UI notes (verified against actual templates):
- Bottom sheets: data-bottom-sheet="create-sheet", "account-sheet", "delete-sheet"
  Content areas: #create-sheet-content, #account-sheet-content, #delete-sheet-content
  (loaded via HTMX on sheet open — wait for the form to appear before interacting)
- Add Institution: button with text "+ Institution", onclick="openCreateSheet()"
- Add Account: button with text "+ Account" inside institution card
- Delete institution: trash icon button → opens delete-sheet, confirm via #delete-confirm-btn
- Delete confirm input: id="delete-confirm-input" (not name="confirm_name")
"""
import re
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from playwright.sync_api import Page, expect
from conftest import (
    create_account,
    create_institution,
    ensure_auth,
    reset_database,
    seed_basic_data,
)


@pytest.fixture(scope="module", autouse=True)
def db() -> None:
    reset_database()


@pytest.fixture(autouse=True)
def auth(page: Page) -> None:
    ensure_auth(page)


class TestInstitutions:
    def test_accounts_page_shows_empty_state(self, page: Page) -> None:
        page.goto("/accounts")
        expect(page.locator("main")).to_contain_text("No institutions")

    def test_create_institution_via_bottom_sheet(self, page: Page) -> None:
        page.goto("/accounts")
        page.click('button:has-text("+ Institution")')
        sheet = page.locator('[data-bottom-sheet="create-sheet"]')
        expect(sheet).not_to_have_class(re.compile(r"translate-y-full"))

        # Wait for HTMX to load the form into the sheet content area.
        # The form now uses a combobox: type to search, then select a preset.
        content = page.locator("#create-sheet-content")
        search = content.locator('#preset-search')
        search.wait_for(timeout=5000)  # Ensure HTMX has loaded
        search.fill("HSBC Egypt")  # Match the full preset name for filtering
        search.dispatch_event("input")  # Trigger the combobox filter logic
        # data-preset-option uses preset.value abbreviation ("HSBC"), not the full name
        content.locator('[data-preset-option="HSBC Egypt"]').click()
        with page.expect_response(lambda r: "/institutions/add" in r.url):
            content.locator('button[type="submit"]').click()

        expect(page.locator("main")).to_contain_text("HSBC")

    def test_delete_institution_requires_name_confirmation(self, page: Page) -> None:
        # Create a unique institution for this test to avoid ambiguity with other
        # institutions created in the same module run.
        inst_id = create_institution(page, "Delete Bank")
        page.goto("/accounts")
        # Scope to the specific institution card to avoid strict-mode ambiguity
        page.locator(f'#institution-{inst_id}').locator('[title="Delete institution"]').click()
        content = page.locator("#delete-sheet-content")
        content.locator('#delete-confirm-input').wait_for(timeout=10000)
        delete_btn = content.locator('#delete-confirm-btn')
        expect(delete_btn).to_be_disabled()

        content.locator('#delete-confirm-input').fill("Delete Bank")
        content.locator('#delete-confirm-input').dispatch_event("input")
        expect(delete_btn).to_be_enabled()

    def test_dismiss_sheet_via_cancel(self, page: Page) -> None:
        page.goto("/accounts")
        page.click('button:has-text("+ Institution")')
        sheet = page.locator('[data-bottom-sheet="create-sheet"]')
        expect(sheet).not_to_have_class(re.compile(r"translate-y-full"))

        page.locator("#create-sheet-content").locator('button:has-text("Cancel")').click()
        expect(sheet).to_have_class(re.compile(r"translate-y-full"))


class TestAccounts:
    def test_create_current_account(self, page: Page) -> None:
        page.goto("/accounts")
        create_institution(page, "Test Bank")
        # Reload so the institution card (and "+ Account" button) is visible
        page.goto("/accounts")

        # "+ Account" button appears inside institution card after institution exists
        page.click('button:has-text("+ Account")')
        sheet_content = page.locator("#account-sheet-content")
        # Account name is optional and hidden under "Custom name" toggle — expand first
        sheet_content.locator('button:has-text("Custom name")').click()
        sheet_content.locator('input[name="name"]').fill("My Savings")
        sheet_content.locator('select[name="type"]').select_option("savings")
        sheet_content.locator('input[name="initial_balance"]').fill("5000")

        with page.expect_response(lambda r: "/accounts/add" in r.url):
            sheet_content.locator('button[type="submit"]').click()

        expect(page.locator("main")).to_contain_text("My Savings")

    def test_credit_card_shows_credit_limit_field(self, page: Page) -> None:
        page.goto("/accounts")
        page.click('button:has-text("+ Account")')
        sheet_content = page.locator("#account-sheet-content")

        sheet_content.locator('select[name="type"]').select_option("credit_card")
        expect(sheet_content.locator("#credit-limit-field")).to_be_visible()

    def test_credit_card_without_limit_shows_error(self, page: Page) -> None:
        page.goto("/accounts")
        page.click('button:has-text("+ Account")')
        sheet_content = page.locator("#account-sheet-content")
        # Name is optional (hidden under Custom name toggle) — skip it here
        sheet_content.locator('select[name="type"]').select_option("credit_card")
        # Don't fill credit_limit — should fail
        sheet_content.locator('button[type="submit"]').click()
        expect(sheet_content.locator(".bg-red-50")).to_be_visible()

    def test_credit_card_error_allows_retry(self, page: Page) -> None:
        page.goto("/accounts")
        page.click('button:has-text("+ Account")')
        sheet_content = page.locator("#account-sheet-content")
        # Name is optional — focus on testing the retry flow itself
        sheet_content.locator('select[name="type"]').select_option("credit_card")
        # Submit without limit → error (HTMX re-renders form with error, all fields reset)
        sheet_content.locator('button[type="submit"]').click()
        expect(sheet_content.locator(".bg-red-50")).to_be_visible()
        # Re-select type (form was re-rendered) and add credit_limit
        type_select = sheet_content.locator('select[name="type"]')
        type_select.select_option("credit_card")
        # Explicitly dispatch change so the inline onchange shows the credit-limit field
        type_select.dispatch_event("change")
        expect(sheet_content.locator("#credit-limit-field")).to_be_visible()
        sheet_content.locator('input[name="credit_limit"]').fill("100000")
        with page.expect_response(lambda r: "/accounts/add" in r.url):
            sheet_content.locator('button[type="submit"]').click()
        # Auto-generated name is "{Institution} - Credit Card"
        expect(page.locator("main")).to_contain_text("Credit Card")

    def test_account_detail_page_shows_balance(self, page: Page) -> None:
        _, account_id = seed_basic_data(page)
        page.goto(f"/accounts/{account_id}")
        expect(page.locator("main")).to_contain_text("10,000")

    def test_dormant_toggle_redirects(self, page: Page) -> None:
        _, account_id = seed_basic_data(page)
        page.goto(f"/accounts/{account_id}")
        # HTMX dormant button (no name attr) — triggers HX-Redirect back to same page
        page.click('button:has-text("Dormant")')
        page.wait_for_url(re.compile(rf"/accounts/{account_id}"))
        expect(page).to_have_url(re.compile(rf"/accounts/{account_id}"))
