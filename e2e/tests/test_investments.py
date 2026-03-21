"""Investment portfolio tests.

Converts: 08-investments.spec.ts

UI notes:
- Add form: hx-post="/investments/add", fields: platform, fund_name, units, unit_price
- Update: POST to /investments/{id}/update, button text "Update"
- Delete: hx-delete with hx-confirm, button text "Del"
- Empty state: "No investments yet."
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


class TestInvestments:
    def test_empty_state(self, page: Page) -> None:
        page.goto("/investments")
        expect(page.locator("main")).to_contain_text("No investments yet")

    def test_add_fund(self, page: Page) -> None:
        page.goto("/investments")
        page.fill('input[name="fund_name"]', "Vanguard S&P 500")
        page.fill('input[name="units"]', "10")
        page.fill('input[name="unit_price"]', "500")
        with page.expect_response(
            lambda r: "/investments/add" in r.url and r.request.method == "POST"
        ):
            page.click('button[type="submit"]')
        expect(page.locator("main")).to_contain_text("Vanguard S&P 500")

    def test_update_valuation(self, page: Page) -> None:
        page.goto("/investments")
        # Target the per-investment update form (not the add-investment form at the top)
        update_form = page.locator('form[hx-post*="/update"]')
        update_form.locator('input[name="unit_price"]').fill("600")
        with page.expect_response(lambda r: "/update" in r.url and r.request.method == "POST"):
            update_form.locator('button[type="submit"]').click()
        # Total value: 10 units × 600 = 6,000
        expect(page.locator("main")).to_contain_text("6,000")

    def test_delete_investment(self, page: Page) -> None:
        page.goto("/investments")
        # Del button uses hx-confirm which fires a browser dialog
        page.on("dialog", lambda d: d.accept())
        with page.expect_response(lambda r: "/investments/" in r.url and r.request.method == "DELETE"):
            page.click('button:has-text("Del")')
        expect(page.locator("main")).to_contain_text("No investments yet")
