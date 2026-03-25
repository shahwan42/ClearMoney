"""Reports page and settings tests.

Converts: 10-reports-settings.spec.ts
Covers: reports month navigation, Fawry cashout, batch entry, settings page.
"""
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

_user_id: str = ""


@pytest.fixture(scope="function", autouse=True)
def db() -> None:
    """Reset DB and create test institution + account via SQL."""
    global _user_id
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
                " VALUES (%s, %s, 'Current', 'current', 'EGP', 10000, 10000, 0) RETURNING id",
                (_user_id, inst_id),
            )
        conn.commit()


@pytest.fixture(autouse=True)
def auth(page: Page) -> None:
    ensure_auth(page)


class TestReports:
    def test_reports_page_loads(self, page: Page) -> None:
        page.goto("/reports")
        expect(page.locator("main")).to_be_visible()

    def test_month_navigation_previous(self, page: Page) -> None:
        page.goto("/reports")
        # Navigation is <a> links, not buttons (renders "← Prev" and "Next →")
        with page.expect_response(lambda r: "/reports" in r.url):
            page.click('a:has-text("Prev")')
        expect(page.locator("main")).to_be_visible()

    def test_month_navigation_next(self, page: Page) -> None:
        page.goto("/reports")
        page.click('a:has-text("Prev")')
        with page.expect_response(lambda r: "/reports" in r.url):
            page.click('a:has-text("Next")')
        expect(page.locator("main")).to_be_visible()


class TestFawryCashout:
    def test_fawry_page_loads(self, page: Page) -> None:
        # /fawry-cashout redirects to /transfers/new
        page.goto("/fawry-cashout")
        expect(page.locator("#transfer-amount")).to_be_visible()

    def test_transfer_fee_total_display(self, page: Page) -> None:
        page.goto("/transfers/new")
        page.fill("#transfer-amount", "1000")
        page.fill("#transfer-fee", "10")
        page.wait_for_timeout(300)
        # Fee > 0 shows the total display
        expect(page.locator("#transfer-total-display")).to_be_visible()


class TestBatchEntry:
    def test_batch_entry_page_shows_rows(self, page: Page) -> None:
        # Batch entry is at /batch-entry (not /transactions/batch)
        page.goto("/batch-entry")
        expect(page.locator(".batch-row")).to_have_count(1)


class TestSettings:
    def test_settings_page_loads(self, page: Page) -> None:
        page.goto("/settings")
        expect(page.locator("main")).to_be_visible()

    def test_csv_export_button_visible(self, page: Page) -> None:
        page.goto("/settings")
        expect(page.locator('button:has-text("Download CSV")')).to_be_visible()

    def test_exchange_rates_page_loads(self, page: Page) -> None:
        page.goto("/exchange-rates")
        expect(page.locator("main")).to_be_visible()

    def test_logout_button_visible_in_settings(self, page: Page) -> None:
        page.goto("/settings")
        expect(page.locator('button:has-text("Log Out")').first).to_be_visible()
