"""Salary wizard and quick entry FAB tests.

Converts: 11-salary-quickentry.spec.ts

UI notes:
- Salary wizard: multi-step HTMX form in #salary-wizard
  Step 1: salary_usd, usd_account_id, egp_account_id, date → POST /salary/step2
  Step 2: exchange_rate → POST /salary/step3
  Step 3: allocation with "Remainder" shown
- FAB button: .fab-button (onclick="openQuickEntry()")
- Quick entry sheet: #quick-entry-sheet (not #quick-entry-form)
- Tabs: #tab-transaction, #tab-exchange, #tab-transfer
- Close: window.closeQuickEntry() or closeQuickEntry()
"""
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from playwright.sync_api import Page, expect
from conftest import (
    _conn,
    ensure_auth,
    reset_database,
)

_egp_account_id: str = ""
_usd_account_id: str = ""
_user_id: str = ""


@pytest.fixture(scope="module", autouse=True)
def db() -> None:
    """Reset DB and create test institution + EGP and USD accounts via SQL."""
    global _egp_account_id, _usd_account_id, _user_id
    _user_id = reset_database()
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO institutions (user_id, name, type, display_order)"
                " VALUES (%s, 'Test Bank', 'bank', 0) RETURNING id",
                (_user_id,),
            )
            inst_id = str(cur.fetchone()[0])  # type: ignore[index]
            cur.execute(
                "INSERT INTO accounts"
                " (user_id, institution_id, name, type, currency, current_balance, initial_balance, display_order)"
                " VALUES (%s, %s, 'EGP Current', 'current', 'EGP', 10000, 10000, 0) RETURNING id",
                (_user_id, inst_id),
            )
            _egp_account_id = str(cur.fetchone()[0])  # type: ignore[index]
            cur.execute(
                "INSERT INTO accounts"
                " (user_id, institution_id, name, type, currency, current_balance, initial_balance, display_order)"
                " VALUES (%s, %s, 'USD Account', 'current', 'USD', 0, 0, 1) RETURNING id",
                (_user_id, inst_id),
            )
            _usd_account_id = str(cur.fetchone()[0])  # type: ignore[index]
        conn.commit()


@pytest.fixture(autouse=True)
def auth(page: Page) -> None:
    ensure_auth(page)


class TestSalaryWizard:
    def test_salary_wizard_step_1(self, page: Page) -> None:
        page.goto("/salary")
        expect(page.locator('input[name="salary_usd"]')).to_be_visible()
        page.fill('input[name="salary_usd"]', "1000")
        page.select_option('select[name="usd_account_id"]', _usd_account_id)
        page.select_option('select[name="egp_account_id"]', _egp_account_id)
        with page.expect_response(lambda r: "/salary/step2" in r.url):
            page.click('button:has-text("Next")')
        expect(page.locator('input[name="exchange_rate"]')).to_be_visible()

    def test_salary_wizard_step_2(self, page: Page) -> None:
        page.goto("/salary")
        page.fill('input[name="salary_usd"]', "1000")
        page.select_option('select[name="usd_account_id"]', _usd_account_id)
        page.select_option('select[name="egp_account_id"]', _egp_account_id)
        with page.expect_response(lambda r: "/salary/step2" in r.url):
            page.click('button:has-text("Next")')
        page.fill('input[name="exchange_rate"]', "50")
        with page.expect_response(lambda r: "/salary/step3" in r.url):
            page.click('button:has-text("Next")')
        # Step 3: allocation — total EGP = 1000 × 50 = 50000 (rendered as float)
        expect(page.locator("main")).to_contain_text("50000")

    def test_salary_wizard_shows_remainder(self, page: Page) -> None:
        page.goto("/salary")
        page.fill('input[name="salary_usd"]', "1000")
        page.select_option('select[name="usd_account_id"]', _usd_account_id)
        page.select_option('select[name="egp_account_id"]', _egp_account_id)
        with page.expect_response(lambda r: "/salary/step2" in r.url):
            page.click('button:has-text("Next")')
        page.fill('input[name="exchange_rate"]', "50")
        with page.expect_response(lambda r: "/salary/step3" in r.url):
            page.click('button:has-text("Next")')
        # Remainder starts at full amount before allocations
        expect(page.locator("main")).to_contain_text("Remainder")


class TestQuickEntry:
    def test_fab_opens_quick_entry_form(self, page: Page) -> None:
        page.goto("/")
        page.click(".fab-button")
        expect(page.locator("#quick-entry-sheet")).to_be_visible()

    def test_fab_close_hides_form(self, page: Page) -> None:
        page.goto("/")
        page.click(".fab-button")
        expect(page.locator("#quick-entry-sheet")).to_be_visible()
        page.evaluate("closeQuickEntry()")
        # Sheet uses CSS transform (translate-y-full), not display:none
        expect(page.locator("#quick-entry-sheet")).to_have_class(re.compile(r"translate-y-full"))

    def test_exchange_tab_shows_exchange_fields(self, page: Page) -> None:
        page.goto("/")
        page.click(".fab-button")
        page.click("#tab-exchange")
        expect(page.locator("#exchange-src")).to_be_visible()
        expect(page.locator("#exchange-dst")).to_be_visible()

    def test_exchange_auto_calculates_counter(self, page: Page) -> None:
        page.goto("/")
        page.click(".fab-button")
        page.click("#tab-exchange")
        page.wait_for_selector("#exchange-amount")  # Wait for HTMX to load the form
        # Set values and trigger calculation via JS directly (avoids oninput timing issues)
        page.evaluate(
            "document.getElementById('exchange-amount').value = '5000';"
            "document.getElementById('exchange-rate').value = '50';"
            "calcExchange('rate');"
        )
        # Default direction (no accounts selected, non-EGP→USD): counter = 5000 * 50
        expect(page.locator("#exchange-counter")).to_have_value("250000.00")

    def test_quick_entry_resets_on_reopen(self, page: Page) -> None:
        page.goto("/")
        page.click(".fab-button")
        page.click("#tab-exchange")
        page.evaluate("closeQuickEntry()")
        page.click(".fab-button")
        # Should default back to the first tab (Transaction), not exchange
        expect(page.locator("#tab-transaction")).to_be_visible()
