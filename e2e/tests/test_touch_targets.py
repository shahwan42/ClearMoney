"""Touch target compliance tests — WCAG 2.5.5 (44×44px minimum).

Tests verify interactive elements meet the 44×44px minimum touch target size
at the 375px mobile viewport (iPhone SE baseline).
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from playwright.sync_api import Page
from conftest import ensure_auth, reset_database

MIN_TARGET = 44  # WCAG AAA minimum touch target size in pixels


def _measure(page: Page, selector: str) -> dict:
    """Return width and height of the element matching selector."""
    return page.evaluate(
        """(sel) => {
            const el = document.querySelector(sel);
            if (!el) return null;
            const r = el.getBoundingClientRect();
            return { w: Math.round(r.width), h: Math.round(r.height) };
        }""",
        selector,
    )


@pytest.fixture(scope="module", autouse=True)
def db() -> None:
    reset_database()


@pytest.fixture(autouse=True)
def auth(page: Page) -> None:
    ensure_auth(page)


@pytest.fixture(autouse=True)
def mobile_viewport(page: Page) -> None:
    """Set 375px mobile viewport for all tests in this module."""
    page.set_viewport_size({"width": 375, "height": 667})


class TestBottomNavTouchTargets:
    """Bottom navigation items must be at least 44×44px."""

    def test_home_nav_item_min_44x44(self, page: Page) -> None:
        page.goto("/")
        size = _measure(page, 'nav[aria-label="Main navigation"] a[href="/"]')
        assert size is not None, "Home nav item not found"
        assert size["w"] >= MIN_TARGET, f"Home nav width {size['w']}px < {MIN_TARGET}px"
        assert size["h"] >= MIN_TARGET, f"Home nav height {size['h']}px < {MIN_TARGET}px"

    def test_history_nav_item_min_44x44(self, page: Page) -> None:
        page.goto("/")
        size = _measure(page, 'nav[aria-label="Main navigation"] a[href="/transactions"]')
        assert size is not None, "History nav item not found"
        assert size["w"] >= MIN_TARGET, f"History nav width {size['w']}px < {MIN_TARGET}px"
        assert size["h"] >= MIN_TARGET, f"History nav height {size['h']}px < {MIN_TARGET}px"

    def test_accounts_nav_item_min_44x44(self, page: Page) -> None:
        page.goto("/")
        size = _measure(page, 'nav[aria-label="Main navigation"] a[href="/accounts"]')
        assert size is not None, "Accounts nav item not found"
        assert size["w"] >= MIN_TARGET, f"Accounts nav width {size['w']}px < {MIN_TARGET}px"
        assert size["h"] >= MIN_TARGET, f"Accounts nav height {size['h']}px < {MIN_TARGET}px"

    def test_more_button_min_44x44(self, page: Page) -> None:
        page.goto("/")
        size = _measure(page, 'button[aria-label="More menu"]')
        assert size is not None, "More menu button not found"
        assert size["w"] >= MIN_TARGET, f"More button width {size['w']}px < {MIN_TARGET}px"
        assert size["h"] >= MIN_TARGET, f"More button height {size['h']}px < {MIN_TARGET}px"

    def test_fab_button_min_44x44(self, page: Page) -> None:
        page.goto("/")
        size = _measure(page, 'button[aria-label="Add transaction"]')
        assert size is not None, "FAB button not found"
        assert size["w"] >= MIN_TARGET, f"FAB width {size['w']}px < {MIN_TARGET}px"
        assert size["h"] >= MIN_TARGET, f"FAB height {size['h']}px < {MIN_TARGET}px"


class TestQuickEntryTabTouchTargets:
    """Quick entry sheet tab buttons must be at least 44px tall."""

    def test_quick_entry_tabs_min_44px_height(self, page: Page) -> None:
        page.goto("/")
        # Open the quick entry sheet
        page.click('button[aria-label="Add transaction"]')
        page.wait_for_selector("#quick-entry-sheet:not(.translate-y-full)", timeout=3000)

        for tab_id in ("tab-transaction", "tab-exchange", "tab-transfer"):
            size = _measure(page, f"#{tab_id}")
            assert size is not None, f"Tab #{tab_id} not found"
            assert size["h"] >= MIN_TARGET, (
                f"Quick entry tab #{tab_id} height {size['h']}px < {MIN_TARGET}px"
            )


class TestHeaderTouchTargets:
    """Header icon buttons must be at least 44×44px."""

    def test_dark_mode_toggle_min_44x44(self, page: Page) -> None:
        page.goto("/")
        size = _measure(page, "#theme-toggle")
        assert size is not None, "Dark mode toggle not found"
        assert size["w"] >= MIN_TARGET, f"Toggle width {size['w']}px < {MIN_TARGET}px"
        assert size["h"] >= MIN_TARGET, f"Toggle height {size['h']}px < {MIN_TARGET}px"

    def test_header_accounts_link_min_44x44(self, page: Page) -> None:
        page.goto("/")
        size = _measure(page, 'header a[href="/accounts"]')
        assert size is not None, "Header accounts link not found"
        assert size["w"] >= MIN_TARGET, f"Header accounts width {size['w']}px < {MIN_TARGET}px"
        assert size["h"] >= MIN_TARGET, f"Header accounts height {size['h']}px < {MIN_TARGET}px"

    def test_header_reports_link_min_44x44(self, page: Page) -> None:
        page.goto("/")
        size = _measure(page, 'header a[href="/reports"]')
        assert size is not None, "Header reports link not found"
        assert size["w"] >= MIN_TARGET, f"Header reports width {size['w']}px < {MIN_TARGET}px"
        assert size["h"] >= MIN_TARGET, f"Header reports height {size['h']}px < {MIN_TARGET}px"

    def test_header_settings_link_min_44x44(self, page: Page) -> None:
        page.goto("/")
        size = _measure(page, 'header a[href="/settings"]')
        assert size is not None, "Header settings link not found"
        assert size["w"] >= MIN_TARGET, f"Header settings width {size['w']}px < {MIN_TARGET}px"
        assert size["h"] >= MIN_TARGET, f"Header settings height {size['h']}px < {MIN_TARGET}px"
