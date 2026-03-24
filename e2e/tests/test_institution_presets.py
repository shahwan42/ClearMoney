"""Institution preset combobox E2E tests.

Tests that the institution creation form shows a searchable preset combobox
for all three institution types (bank, fintech, wallet), auto-fills the name,
and persists the icon and color on submission.
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
    """Navigate to /accounts and open the add-institution bottom sheet."""
    page.goto("/accounts")
    page.click('button:has-text("+ Institution")')
    # Wait for HTMX to load the form
    page.locator("#create-sheet-content").locator("#preset-search").wait_for()


class TestBankPresets:
    def test_bank_preset_appears_when_typing(self, page: Page) -> None:
        open_create_sheet(page)
        content = page.locator("#create-sheet-content")
        content.locator("#preset-search").fill("CIB")
        expect(content.locator('[data-preset-option="CIB"]')).to_be_visible()

    def test_bank_preset_option_shows_logo(self, page: Page) -> None:
        open_create_sheet(page)
        content = page.locator("#create-sheet-content")
        content.locator("#preset-search").fill("CIB")
        option = content.locator('[data-preset-option="CIB"]')
        expect(option.locator("img")).to_be_visible()

    def test_bank_preset_fills_name(self, page: Page) -> None:
        open_create_sheet(page)
        content = page.locator("#create-sheet-content")
        content.locator("#preset-search").fill("CIB")
        content.locator('[data-preset-option="CIB"]').click()
        expect(content.locator("#preset-search")).to_have_value("CIB")

    def test_bank_preset_submitted_with_icon_and_color(self, page: Page) -> None:
        open_create_sheet(page)
        content = page.locator("#create-sheet-content")
        content.locator("#preset-search").fill("CIB")
        content.locator('[data-preset-option="CIB"]').click()
        with page.expect_response(lambda r: "/institutions/add" in r.url) as resp:
            content.locator('button[type="submit"]').click()
        assert resp.value.status == 200
        expect(page.locator("main")).to_contain_text("CIB")
        # Institution card should show an <img> (SVG logo)
        expect(page.locator('img[alt="CIB"]')).to_be_visible()


class TestFintechPresets:
    def test_fintech_presets_appear_after_type_change(self, page: Page) -> None:
        open_create_sheet(page)
        content = page.locator("#create-sheet-content")
        content.locator("#inst-type").select_option("fintech")
        content.locator("#preset-search").fill("Telda")
        expect(content.locator('[data-preset-option="Telda"]')).to_be_visible()

    def test_fintech_preset_fills_name(self, page: Page) -> None:
        open_create_sheet(page)
        content = page.locator("#create-sheet-content")
        content.locator("#inst-type").select_option("fintech")
        content.locator("#preset-search").fill("Telda")
        content.locator('[data-preset-option="Telda"]').click()
        expect(content.locator("#preset-search")).to_have_value("Telda")


class TestWalletPresets:
    def test_wallet_shows_physical_and_digital_groups(self, page: Page) -> None:
        open_create_sheet(page)
        content = page.locator("#create-sheet-content")
        content.locator("#inst-type").select_option("wallet")
        content.locator("#preset-search").click()
        expect(content.locator("text=Physical")).to_be_visible()
        expect(content.locator("text=Digital")).to_be_visible()

    def test_physical_wallet_preset_fills_name(self, page: Page) -> None:
        open_create_sheet(page)
        content = page.locator("#create-sheet-content")
        content.locator("#inst-type").select_option("wallet")
        content.locator("#preset-search").fill("Pocket")
        content.locator('[data-preset-option="Pocket Wallet"]').click()
        expect(content.locator("#preset-search")).to_have_value("Pocket Wallet")

    def test_digital_wallet_preset_fills_name(self, page: Page) -> None:
        open_create_sheet(page)
        content = page.locator("#create-sheet-content")
        content.locator("#inst-type").select_option("wallet")
        content.locator("#preset-search").fill("Vodafone")
        content.locator('[data-preset-option="Vodafone Cash"]').click()
        expect(content.locator("#preset-search")).to_have_value("Vodafone Cash")


class TestCustomName:
    def test_other_option_allows_custom_name(self, page: Page) -> None:
        open_create_sheet(page)
        content = page.locator("#create-sheet-content")
        content.locator("#preset-search").fill("My Savings Jar")
        content.locator('[data-preset-option="other"]').click()
        with page.expect_response(lambda r: "/institutions/add" in r.url) as resp:
            content.locator('button[type="submit"]').click()
        assert resp.value.status == 200
        expect(page.locator("main")).to_contain_text("My Savings Jar")
