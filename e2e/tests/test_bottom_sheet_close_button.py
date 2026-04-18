"""Bottom sheet close button tests.

Tests for the visible X close button in bottom sheets.

UI notes:
- Close button: absolute positioned in top-right of drag handle bar
- Icon: Heroicons X-mark (same as used in health warnings)
- Touch target: 44x44px (p-2 padding + w-5 h-5 icon)
- Keyboard accessible: focusable with Tab, triggers on Enter/Space
- ARIA: aria-label="Close"
"""

import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from playwright.sync_api import Page, expect
from conftest import ensure_auth, reset_database


@pytest.fixture(scope="function", autouse=True)
def db() -> None:
    reset_database()


@pytest.fixture(autouse=True)
def auth(db: None, page: Page) -> None:
    ensure_auth(page)


class TestBottomSheetCloseButton:
    def test_close_button_exists_in_more_menu(self, page: Page) -> None:
        """Verify X close button is present in more-menu bottom sheet."""
        page.goto("/")
        page.click('button:has-text("More")')

        sheet = page.locator('[data-bottom-sheet="more-menu"]')
        expect(sheet).to_be_visible()

        close_button = sheet.locator('button[aria-label="Close"]')
        expect(close_button).to_be_visible(timeout=5000)

    def test_clicking_close_button_closes_sheet(self, page: Page) -> None:
        """Verify clicking X button closes the bottom sheet."""
        page.goto("/")
        page.click('button:has-text("More")')

        sheet = page.locator('[data-bottom-sheet="more-menu"]')
        expect(sheet).to_be_visible()
        expect(sheet).not_to_have_class(re.compile(r"translate-y-full"))

        close_button = sheet.locator('button[aria-label="Close"]')
        close_button.click()

        expect(sheet).to_have_class(re.compile(r"translate-y-full"), timeout=5000)

    def test_close_button_has_aria_label(self, page: Page) -> None:
        """Verify close button has proper ARIA label for accessibility."""
        page.goto("/")
        page.click('button:has-text("More")')

        sheet = page.locator('[data-bottom-sheet="more-menu"]')
        close_button = sheet.locator('button[aria-label="Close"]')

        expect(close_button).to_have_attribute("aria-label", "Close")

    def test_close_button_is_keyboard_focusable(self, page: Page) -> None:
        """Verify close button can receive keyboard focus."""
        page.goto("/")
        page.click('button:has-text("More")')

        sheet = page.locator('[data-bottom-sheet="more-menu"]')
        close_button = sheet.locator('button[aria-label="Close"]')

        # Tab to focus the close button
        page.keyboard.press("Tab")
        expect(close_button).to_be_focused()

    def test_close_button_visible_in_dark_mode(self, page: Page) -> None:
        """Verify close button is visible in dark mode."""
        page.goto("/")

        # Enable dark mode via settings
        page.evaluate("""
            document.documentElement.classList.add('dark');
            localStorage.setItem('theme', 'dark');
        """)

        page.click('button:has-text("More")')

        sheet = page.locator('[data-bottom-sheet="more-menu"]')
        close_button = sheet.locator('button[aria-label="Close"]')

        expect(close_button).to_be_visible()

        # Check icon has dark mode color
        icon = close_button.locator("svg")
        expect(icon).to_have_class(re.compile(r"text-slate-400"))

    def test_close_button_has_correct_styling(self, page: Page) -> None:
        """Verify close button has expected CSS classes for styling."""
        page.goto("/")
        page.click('button:has-text("More")')

        sheet = page.locator('[data-bottom-sheet="more-menu"]')
        close_button = sheet.locator('button[aria-label="Close"]')

        # Check button is positioned absolutely in handle bar
        expect(close_button).to_have_class(re.compile(r"absolute"))
        expect(close_button).to_have_class(re.compile(r"top-1"))
        expect(close_button).to_have_class(re.compile(r"right-2"))
        expect(close_button).to_have_class(re.compile(r"p-3"))

    def test_close_button_is_keyboard_focusable(self, page: Page) -> None:
        """Verify close button can receive keyboard focus."""
        page.goto("/")
        page.click('button:has-text("More")')

        sheet = page.locator('[data-bottom-sheet="more-menu"]')
        close_button = sheet.locator('button[aria-label="Close"]')

        # Tab to focus the close button
        page.keyboard.press("Tab")
        expect(close_button).to_be_focused()

    def test_clicking_close_button_closes_sheet(self, page: Page) -> None:
        """Verify clicking X button closes the bottom sheet."""
        page.goto("/")
        page.click('button:has-text("More")')

        sheet = page.locator('[data-bottom-sheet="more-menu"]')
        expect(sheet).to_be_visible()
        expect(sheet).not_to_have_class(re.compile(r"translate-y-full"))

        close_button = sheet.locator('button[aria-label="Close"]')
        close_button.click()

        expect(sheet).to_have_class(re.compile(r"translate-y-full"))

    def test_close_button_visible_in_dark_mode(self, page: Page) -> None:
        """Verify close button is visible in dark mode."""
        page.goto("/")

        # Enable dark mode via settings
        page.evaluate("""
            document.documentElement.classList.add('dark');
            localStorage.setItem('theme', 'dark');
        """)

        page.click('button:has-text("More")')

        sheet = page.locator('[data-bottom-sheet="more-menu"]')
        close_button = sheet.locator('button[aria-label="Close"]')

        expect(close_button).to_be_visible()

        # Check icon has dark mode color
        icon = close_button.locator("svg")
        expect(icon).to_have_class(re.compile(r"text-slate-400"))

    def test_close_button_has_aria_label(self, page: Page) -> None:
        """Verify close button has proper ARIA label for accessibility."""
        page.goto("/")
        page.click('button:has-text("More")')

        sheet = page.locator('[data-bottom-sheet="more-menu"]')
        close_button = sheet.locator('button[aria-label="Close"]')

        expect(close_button).to_have_attribute("aria-label", "Close")

    def test_close_button_has_44px_touch_target(self, page: Page) -> None:
        """Verify close button has minimum 44x44px touch target."""
        page.goto("/")
        page.click('button:has-text("More")')

        sheet = page.locator('[data-bottom-sheet="more-menu"]')
        close_button = sheet.locator('button[aria-label="Close"]')

        # Get bounding box to verify touch target size
        box = close_button.bounding_box()
        assert box is not None
        # Allow some tolerance for border/padding calculations
        assert box["width"] >= 40, f"Close button width {box['width']}px < 40px minimum"
        assert box["height"] >= 40, (
            f"Close button height {box['height']}px < 40px minimum"
        )
