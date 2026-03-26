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


@pytest.fixture(scope="function", autouse=True)
def db() -> None:
    reset_database()


@pytest.fixture(autouse=True)
def auth(db: None, page: Page) -> None:
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


class TestFormControlTouchTargets:
    """Form inputs, selects, and textareas must be at least 44px tall."""

    def test_account_form_selects_min_44px(self, page: Page) -> None:
        page.goto("/accounts")
        page.click('button:has-text("+ Account")')
        # Wait for HTMX to load the form into the bottom sheet
        page.wait_for_selector('select[name="type"]', timeout=5000)
        selects = page.query_selector_all('select')
        for sel in selects:
            box = sel.bounding_box()
            if box and box["width"] > 0 and box["height"] > 0:
                assert box["height"] >= MIN_TARGET, (
                    f"Select height {box['height']:.0f}px < {MIN_TARGET}px"
                )

    def test_account_form_inputs_min_44px(self, page: Page) -> None:
        page.goto("/accounts")
        page.click('button:has-text("+ Account")')
        # Wait for HTMX to load the form into the bottom sheet
        page.wait_for_selector('input[name="name"]', timeout=5000)
        inputs = page.query_selector_all('input:not([type="radio"]):not([type="checkbox"]):not([type="hidden"])')
        for inp in inputs:
            box = inp.bounding_box()
            if box and box["width"] > 0 and box["height"] > 0:
                assert box["height"] >= MIN_TARGET, (
                    f"Input (type={inp.get_attribute('type') or 'text'}) height {box['height']:.0f}px < {MIN_TARGET}px"
                )

    def test_settings_date_inputs_min_44px(self, page: Page) -> None:
        page.goto("/settings")
        date_inputs = page.query_selector_all('input[type="date"]')
        for inp in date_inputs:
            box = inp.bounding_box()
            if box and box["width"] > 0 and box["height"] > 0:
                assert box["height"] >= MIN_TARGET, (
                    f"Date input height {box['height']:.0f}px < {MIN_TARGET}px"
                )

    def test_settings_buttons_min_44px(self, page: Page) -> None:
        page.goto("/settings")
        # Check all interactive buttons in main content are ≥44px
        buttons = page.query_selector_all('main button')
        for btn in buttons:
            box = btn.bounding_box()
            if box and box["width"] > 0 and box["height"] > 0:
                assert box["height"] >= MIN_TARGET, (
                    f"Settings button '{btn.inner_text()[:20]}' height {box['height']:.0f}px < {MIN_TARGET}px"
                )
                assert box["width"] >= MIN_TARGET, (
                    f"Settings button '{btn.inner_text()[:20]}' width {box['width']:.0f}px < {MIN_TARGET}px"
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


class TestEmptyStateTouchTargets:
    """Empty-state CTAs must be at least 44×44px."""

    def test_dashboard_empty_state_cta_min_44px(self, page: Page) -> None:
        page.goto("/")
        size = _measure(page, 'a[href="/accounts"]')
        # May not render if user has accounts; skip if absent
        if size is None:
            return
        assert size["h"] >= MIN_TARGET, (
            f"Dashboard empty-state CTA height {size['h']}px < {MIN_TARGET}px"
        )

    def test_transactions_empty_state_cta_min_44px(self, page: Page) -> None:
        page.goto("/transactions")
        size = _measure(page, 'button[onclick="openQuickEntry()"]')
        if size is None:
            return
        assert size["h"] >= MIN_TARGET, (
            f"Transactions empty-state button height {size['h']}px < {MIN_TARGET}px"
        )

    def test_reports_empty_state_cta_min_44px(self, page: Page) -> None:
        page.goto("/reports")
        size = _measure(page, 'a[href="/transactions/new"]')
        if size is None:
            return
        assert size["h"] >= MIN_TARGET, (
            f"Reports empty-state CTA height {size['h']}px < {MIN_TARGET}px"
        )


class TestSettingsLinkTouchTargets:
    """Settings page links must be at least 44px tall."""

    def test_categories_link_min_44px(self, page: Page) -> None:
        page.goto("/settings")
        size = _measure(page, 'a[href="/settings/categories"]')
        assert size is not None, "Categories link not found"
        assert size["h"] >= MIN_TARGET, (
            f"Categories link height {size['h']}px < {MIN_TARGET}px"
        )

    def test_quick_links_min_44px(self, page: Page) -> None:
        page.goto("/settings")
        for href in ("/budgets", "/investments", "/recurring", "/virtual-accounts"):
            size = _measure(page, f'a[href="{href}"]')
            assert size is not None, f"Quick link {href} not found"
            assert size["h"] >= MIN_TARGET, (
                f"Quick link {href} height {size['h']}px < {MIN_TARGET}px"
            )


class TestReportsNavTouchTargets:
    """Reports pagination and utility links must be at least 44px tall."""

    def test_reports_prev_next_links_min_44px(self, page: Page) -> None:
        page.goto("/reports")
        # Find Prev/Next by text content (querySelector doesn't support :has-text)
        for text, name in (("Prev", "Prev"), ("Next", "Next")):
            size = page.evaluate(
                """(t) => {
                    const links = [...document.querySelectorAll('a')];
                    const el = links.find(a => a.textContent.includes(t));
                    if (!el) return null;
                    const r = el.getBoundingClientRect();
                    return { w: Math.round(r.width), h: Math.round(r.height) };
                }""",
                text,
            )
            if size is None:
                continue
            assert size["h"] >= MIN_TARGET, (
                f"Reports {name} link height {size['h']}px < {MIN_TARGET}px"
            )

    def test_reports_rate_history_link_min_44px(self, page: Page) -> None:
        page.goto("/reports")
        size = _measure(page, 'a[href="/exchange-rates"]')
        if size is None:
            return
        assert size["h"] >= MIN_TARGET, (
            f"Rate History link height {size['h']}px < {MIN_TARGET}px"
        )


class TestCategoriesPageTouchTargets:
    """Categories page buttons and links must be at least 44px tall."""

    def test_back_link_min_44px(self, page: Page) -> None:
        page.goto("/settings/categories")
        size = _measure(page, 'a[href="/settings"]')
        assert size is not None, "Back link not found"
        assert size["h"] >= MIN_TARGET, (
            f"Back link height {size['h']}px < {MIN_TARGET}px"
        )

    def test_add_category_button_min_44px(self, page: Page) -> None:
        page.goto("/settings/categories")
        size = _measure(page, 'button[type="submit"]')
        assert size is not None, "Add Category button not found"
        assert size["h"] >= MIN_TARGET, (
            f"Add Category button height {size['h']}px < {MIN_TARGET}px"
        )


class TestSecondaryPageTouchTargets:
    """Buttons and nav links on secondary feature pages must be at least 44px."""

    def test_budgets_settings_link_min_44px(self, page: Page) -> None:
        page.goto("/budgets")
        size = _measure(page, 'a[href="/settings"]')
        assert size is not None, "Budgets Settings link not found"
        assert size["h"] >= MIN_TARGET, (
            f"Budgets Settings link height {size['h']}px < {MIN_TARGET}px"
        )

    def test_budgets_create_button_min_44px(self, page: Page) -> None:
        page.goto("/budgets")
        size = _measure(page, 'button[type="submit"]')
        assert size is not None, "Budgets Create Budget button not found"
        assert size["h"] >= MIN_TARGET, (
            f"Budgets Create Budget button height {size['h']}px < {MIN_TARGET}px"
        )

    def test_people_add_button_min_44px(self, page: Page) -> None:
        page.goto("/people")
        size = _measure(page, 'button[type="submit"]')
        assert size is not None, "People Add button not found"
        assert size["h"] >= MIN_TARGET, (
            f"People Add button height {size['h']}px < {MIN_TARGET}px"
        )

    def test_investments_add_button_min_44px(self, page: Page) -> None:
        page.goto("/investments")
        size = _measure(page, 'button[type="submit"]')
        assert size is not None, "Investments Add Investment button not found"
        assert size["h"] >= MIN_TARGET, (
            f"Investments Add Investment button height {size['h']}px < {MIN_TARGET}px"
        )

    def test_virtual_accounts_dashboard_link_min_44px(self, page: Page) -> None:
        page.goto("/virtual-accounts")
        # Find by text to avoid matching the header logo link (also href="/")
        size = page.evaluate(
            """() => {
                const links = [...document.querySelectorAll('main a[href="/"]')];
                if (!links.length) return null;
                const r = links[0].getBoundingClientRect();
                return { w: Math.round(r.width), h: Math.round(r.height) };
            }"""
        )
        assert size is not None, "Virtual Accounts Dashboard link not found"
        assert size["h"] >= MIN_TARGET, (
            f"Virtual Accounts Dashboard link height {size['h']}px < {MIN_TARGET}px"
        )

    def test_virtual_accounts_create_button_min_44px(self, page: Page) -> None:
        page.goto("/virtual-accounts")
        size = _measure(page, 'button[type="submit"]')
        assert size is not None, "Virtual Accounts Create button not found"
        assert size["h"] >= MIN_TARGET, (
            f"Virtual Accounts Create button height {size['h']}px < {MIN_TARGET}px"
        )
