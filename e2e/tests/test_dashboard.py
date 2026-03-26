"""Dashboard rendering tests.

Converts: 04-dashboard.spec.ts
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from playwright.sync_api import Page, expect
from conftest import (
    TEST_EMAIL,
    _conn,
    create_transaction,
    ensure_auth,
    get_category_id,
    reset_database,
    seed_basic_data,
)

_user_id: str = ""


@pytest.fixture(scope="function", autouse=True)
def db() -> None:
    global _user_id
    _user_id = reset_database()


@pytest.fixture(autouse=True)
def auth(db: None, page: Page) -> None:
    ensure_auth(page)


class TestDashboard:
    def test_net_worth_section_visible(self, page: Page) -> None:
        seed_basic_data(page)
        page.goto("/")
        expect(page.locator("main")).to_contain_text("Net Worth")
        expect(page.locator("main")).to_contain_text("10,000")

    def test_summary_cards_visible(self, page: Page) -> None:
        seed_basic_data(page)
        page.goto("/")
        expect(page.locator("main")).to_contain_text("Liquid Cash")
        expect(page.locator("main")).to_contain_text("Credit Used")
        expect(page.locator("main")).to_contain_text("Credit Available")

    def test_institution_accounts_section(self, page: Page) -> None:
        seed_basic_data(page)
        page.goto("/")
        expect(page.locator("main")).to_contain_text("Test Bank")

    def test_recent_transactions_empty_then_populated(self, page: Page) -> None:
        _, account_id = seed_basic_data(page)
        # After seeding data but no transactions, should show "No transactions yet"
        page.goto("/")
        expect(page.locator("main")).to_contain_text("No transactions yet")

        category_id = get_category_id("expense", _user_id)
        create_transaction(page, account_id, category_id, "250", "expense", note="Lunch")

        page.reload()
        expect(page.locator("main")).to_contain_text("Lunch")

    def test_momentum_scroll_content_visible(self, page: Page) -> None:
        """Verify content remains visible during fast momentum scrolling.

        Momentum scrolling can cause rendering jank if touch handlers
        interfere with scroll optimizations. This test ensures content
        doesn't flicker during rapid scrolling.
        """
        seed_basic_data(page)
        page.goto("/")

        # Capture initial content visibility
        net_worth = page.locator("main").get_by_text("Net Worth")
        expect(net_worth).to_be_visible()

        # Simulate fast upward swipe (momentum scroll)
        # On mobile, this would be a quick swipe down gesture
        main = page.locator("main")
        box = main.bounding_box()
        if box:
            # Simulate momentum scroll: quick swipe down at bottom of viewport
            # This triggers momentum scroll upward
            page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] - 50)
            page.mouse.wheel(0, -300)  # Rapid wheel scroll
            page.wait_for_timeout(100)  # Brief pause for momentum
            page.mouse.wheel(0, -300)  # Another rapid scroll

        # Content should remain visible throughout scroll
        expect(net_worth).to_be_visible()

        # Verify key dashboard sections are still rendered
        expect(page.locator("main")).to_contain_text("Liquid Cash")
        expect(page.locator("main")).to_contain_text("Test Bank")
