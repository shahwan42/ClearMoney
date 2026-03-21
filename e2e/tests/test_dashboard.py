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


@pytest.fixture(scope="module", autouse=True)
def db() -> None:
    global _user_id
    _user_id = reset_database()


@pytest.fixture(autouse=True)
def auth(page: Page) -> None:
    ensure_auth(page)


class TestDashboard:
    def test_net_worth_section_visible(self, page: Page) -> None:
        seed_basic_data(page)
        page.goto("/")
        expect(page.locator("main")).to_contain_text("Net Worth")
        expect(page.locator("main")).to_contain_text("10,000")

    def test_summary_cards_visible(self, page: Page) -> None:
        page.goto("/")
        expect(page.locator("main")).to_contain_text("Liquid Cash")
        expect(page.locator("main")).to_contain_text("Credit Used")
        expect(page.locator("main")).to_contain_text("Credit Available")

    def test_institution_accounts_section(self, page: Page) -> None:
        page.goto("/")
        expect(page.locator("main")).to_contain_text("Test Bank")

    def test_recent_transactions_empty_then_populated(self, page: Page) -> None:
        page.goto("/")
        expect(page.locator("main")).to_contain_text("No transactions yet")

        _, account_id = seed_basic_data(page)
        category_id = get_category_id("expense", _user_id)
        create_transaction(page, account_id, category_id, "250", "expense", note="Lunch")

        page.reload()
        expect(page.locator("main")).to_contain_text("Lunch")
