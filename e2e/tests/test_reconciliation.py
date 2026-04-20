"""Balance check workflow E2E tests."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from conftest import _conn, ensure_auth, reset_database
from playwright.sync_api import Page, expect

_account_id: str = ""
_user_id: str = ""


@pytest.fixture(scope="function", autouse=True)
def db() -> None:
    global _account_id, _user_id
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
                " VALUES (%s, %s, 'Checking', 'current', 'EGP', 10000, 10000, 0) RETURNING id",
                (_user_id, inst_id),
            )
            _account_id = str(cur.fetchone()[0])  # type: ignore[index]
        conn.commit()


@pytest.fixture(autouse=True)
def auth(db: None, page: Page) -> None:
    ensure_auth(page)


class TestBalanceCheck:
    def test_balance_check_page_loads(self, page: Page) -> None:
        page.goto(f"/accounts/{_account_id}/balance-check")
        expect(page.locator("main")).to_contain_text("Balance Check")
        expect(page.locator("#bank-balance")).to_be_visible()

    def test_matching_balance_redirects_to_account_detail(self, page: Page) -> None:
        page.goto(f"/accounts/{_account_id}/balance-check")
        page.fill("#bank-balance", "10000")
        with page.expect_navigation():
            page.click("button:has-text('Save Balance Check')")
        expect(page).to_have_url(f"/accounts/{_account_id}", timeout=5000)
        expect(page.locator("main")).to_contain_text("Last checked")

    def test_mismatch_offers_balance_correction(self, page: Page) -> None:
        page.goto(f"/accounts/{_account_id}/balance-check")
        page.fill("#bank-balance", "9700")
        page.click("button:has-text('Save Balance Check')")
        expect(page.locator("main")).to_contain_text("Difference Found")
        expect(page.locator("button:has-text('Create Balance Correction')")).to_be_visible()

    def test_balance_correction_updates_account_balance(self, page: Page) -> None:
        page.goto(f"/accounts/{_account_id}/balance-check")
        page.fill("#bank-balance", "9700")
        page.click("button:has-text('Save Balance Check')")
        with page.expect_navigation():
            page.click("button:has-text('Create Balance Correction')")
        expect(page).to_have_url(f"/accounts/{_account_id}", timeout=5000)
        expect(page.locator("main")).to_contain_text("9,700")

    def test_legacy_reconcile_url_redirects(self, page: Page) -> None:
        page.goto(f"/accounts/{_account_id}/reconcile")
        expect(page).to_have_url(f"/accounts/{_account_id}/balance-check")
