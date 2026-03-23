"""More menu bottom sheet tests.

Converts: 16-more-menu.spec.ts

UI notes:
- More button: <span>More</span> in bottom nav (onclick="openMoreMenu()")
- Sheet: data-bottom-sheet="more-menu" (uses translate-y-full class when closed)
- Overlay: id="more-menu-overlay"
- Links: /people, /budgets, /virtual-accounts, /investments,
  /recurring, /batch-entry, /salary, /fawry-cashout, /settings
"""
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from playwright.sync_api import Page, expect
from conftest import ensure_auth, reset_database

# All navigation links expected in the more menu
_MENU_LINKS = [
    "people", "budgets", "virtual-accounts", "investments",
    "recurring", "batch-entry", "salary",
    "fawry-cashout", "settings",
]


@pytest.fixture(scope="module", autouse=True)
def db() -> None:
    reset_database()


@pytest.fixture(autouse=True)
def auth(page: Page) -> None:
    ensure_auth(page)


class TestMoreMenu:
    def test_more_menu_opens(self, page: Page) -> None:
        page.goto("/")
        menu = page.locator('[data-bottom-sheet="more-menu"]')
        expect(menu).to_have_class(re.compile(r"translate-y-full"))
        page.click('button:has-text("More")')
        expect(menu).not_to_have_class(re.compile(r"translate-y-full"))

    def test_more_menu_contains_all_nav_links(self, page: Page) -> None:
        page.goto("/")
        page.click('button:has-text("More")')
        menu = page.locator('[data-bottom-sheet="more-menu"]')
        for link_path in _MENU_LINKS:
            expect(menu.locator(f'a[href*="{link_path}"]')).to_be_visible()

    def test_overlay_click_dismisses_menu(self, page: Page) -> None:
        page.goto("/")
        page.click('button:has-text("More")')
        menu = page.locator('[data-bottom-sheet="more-menu"]')
        expect(menu).not_to_have_class(re.compile(r"translate-y-full"))
        page.click("#more-menu-overlay")
        expect(menu).to_have_class(re.compile(r"translate-y-full"))

    def test_escape_key_dismisses_menu(self, page: Page) -> None:
        page.goto("/")
        page.click('button:has-text("More")')
        menu = page.locator('[data-bottom-sheet="more-menu"]')
        expect(menu).not_to_have_class(re.compile(r"translate-y-full"))
        page.keyboard.press("Escape")
        expect(menu).to_have_class(re.compile(r"translate-y-full"))
