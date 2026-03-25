"""Institution preset combobox E2E tests.

Tests that the unified add-account form shows a searchable institution preset
combobox for all three institution types (bank, fintech, wallet), auto-fills the
name, and persists the icon and color on submission.

UI notes (current form):
- Header "+ Account" button opens create-sheet with unified institution+account form
- Institution search: #add-acct-inst-search (combobox)
- Preset options: rendered with data-name attribute in #add-acct-preset-list
- Institution type: radio inputs with name="institution_type" (bank/fintech/wallet)
  wrapped in labels — check the radio input to select
- Other option: role="option" with text "Other (custom name)"
- Submits to /accounts/add (not /institutions/add)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from playwright.sync_api import Page, expect
from conftest import ensure_auth, reset_database


@pytest.fixture(scope="module", autouse=True)
def db() -> None:
    reset_database()


@pytest.fixture(autouse=True)
def auth(page: Page) -> None:
    ensure_auth(page)


def open_create_sheet(page: Page) -> None:
    """Navigate to /accounts and open the add-account bottom sheet."""
    page.goto("/accounts")
    page.click('button:has-text("+ Account")')
    # Wait for HTMX to load the unified form
    content = page.locator("#create-sheet-content")
    content.locator("#add-acct-inst-search").wait_for(timeout=10000)


class TestBankPresets:
    def test_bank_preset_appears_when_typing(self, page: Page) -> None:
        open_create_sheet(page)
        content = page.locator("#create-sheet-content")
        search = content.locator("#add-acct-inst-search")
        search.fill("CIB")
        expect(content.locator('[data-name="CIB - Commercial International Bank"]')).to_be_visible()

    def test_bank_preset_option_shows_logo(self, page: Page) -> None:
        open_create_sheet(page)
        content = page.locator("#create-sheet-content")
        search = content.locator("#add-acct-inst-search")
        search.fill("CIB")
        option = content.locator('[data-name="CIB - Commercial International Bank"]')
        expect(option.locator("img")).to_be_visible()

    def test_bank_preset_fills_name(self, page: Page) -> None:
        open_create_sheet(page)
        content = page.locator("#create-sheet-content")
        search = content.locator("#add-acct-inst-search")
        search.fill("CIB")
        content.locator('[data-name="CIB - Commercial International Bank"]').click()
        # After selection, the search input shows the preset's value ("CIB")
        expect(content.locator("#add-acct-inst-search")).to_have_value("CIB")

    def test_bank_preset_submitted_with_icon_and_color(self, page: Page) -> None:
        open_create_sheet(page)
        content = page.locator("#create-sheet-content")
        search = content.locator("#add-acct-inst-search")
        search.fill("CIB")
        content.locator('[data-name="CIB - Commercial International Bank"]').click()
        with page.expect_response(lambda r: "/accounts/add" in r.url) as resp:
            content.locator('button[type="submit"]').click()
        assert resp.value.status == 200
        expect(page.locator("main")).to_contain_text("CIB")
        # Institution card should show an <img> (SVG logo) — check for the icon file
        expect(page.locator('img[src*="cib.svg"]')).to_be_visible()


class TestFintechPresets:
    def test_fintech_presets_appear_after_type_change(self, page: Page) -> None:
        open_create_sheet(page)
        content = page.locator("#create-sheet-content")
        # Select fintech type via radio button
        page.evaluate("() => { const r = document.querySelector('input[name=\"institution_type\"][value=\"fintech\"]'); r.checked = true; r.dispatchEvent(new Event('change', { bubbles: true })); }")
        search = content.locator("#add-acct-inst-search")
        search.fill("Telda")
        expect(content.locator('[data-name="Telda"]')).to_be_visible()

    def test_fintech_preset_fills_name(self, page: Page) -> None:
        open_create_sheet(page)
        content = page.locator("#create-sheet-content")
        page.evaluate("() => { const r = document.querySelector('input[name=\"institution_type\"][value=\"fintech\"]'); r.checked = true; r.dispatchEvent(new Event('change', { bubbles: true })); }")
        search = content.locator("#add-acct-inst-search")
        search.fill("Telda")
        content.locator('[data-name="Telda"]').click()
        expect(content.locator("#add-acct-inst-search")).to_have_value("Telda")


class TestWalletPresets:
    def test_wallet_shows_physical_and_digital_groups(self, page: Page) -> None:
        open_create_sheet(page)
        content = page.locator("#create-sheet-content")
        page.evaluate("() => { const r = document.querySelector('input[name=\"institution_type\"][value=\"wallet\"]'); r.checked = true; r.dispatchEvent(new Event('change', { bubbles: true })); }")
        search = content.locator("#add-acct-inst-search")
        search.click()
        expect(content.locator("text=Physical")).to_be_visible()
        expect(content.locator("text=Digital")).to_be_visible()

    def test_physical_wallet_preset_fills_name(self, page: Page) -> None:
        open_create_sheet(page)
        content = page.locator("#create-sheet-content")
        page.evaluate("() => { const r = document.querySelector('input[name=\"institution_type\"][value=\"wallet\"]'); r.checked = true; r.dispatchEvent(new Event('change', { bubbles: true })); }")
        search = content.locator("#add-acct-inst-search")
        search.fill("Pocket")
        content.locator('[data-name="Pocket Wallet"]').click()
        expect(content.locator("#add-acct-inst-search")).to_have_value("Pocket Wallet")

    def test_digital_wallet_preset_fills_name(self, page: Page) -> None:
        open_create_sheet(page)
        content = page.locator("#create-sheet-content")
        page.evaluate("() => { const r = document.querySelector('input[name=\"institution_type\"][value=\"wallet\"]'); r.checked = true; r.dispatchEvent(new Event('change', { bubbles: true })); }")
        search = content.locator("#add-acct-inst-search")
        search.fill("Vodafone")
        content.locator('[data-name="Vodafone Cash"]').click()
        expect(content.locator("#add-acct-inst-search")).to_have_value("Vodafone Cash")


class TestCustomName:
    def test_other_option_allows_custom_name(self, page: Page) -> None:
        open_create_sheet(page)
        content = page.locator("#create-sheet-content")
        search = content.locator("#add-acct-inst-search")
        search.fill("My Savings Jar")
        # Click "Other (custom name)" option — last item in the listbox
        content.locator('[role="option"]').filter(has_text="Other").click()
        with page.expect_response(lambda r: "/accounts/add" in r.url) as resp:
            content.locator('button[type="submit"]').click()
        assert resp.value.status == 200
        expect(page.locator("main")).to_contain_text("My Savings Jar")
