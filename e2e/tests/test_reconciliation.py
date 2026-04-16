"""Reconciliation workflow E2E tests — T067.

Tests the full reconcile flow: navigate to reconcile page, select transactions,
and complete reconciliation (redirecting to account detail).
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from playwright.sync_api import Page, expect
from conftest import (
    _conn,
    ensure_auth,
    get_category_id,
    reset_database,
)

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

            cat_id_row = cur.execute(
                "SELECT id FROM categories WHERE user_id = %s AND type = 'expense' LIMIT 1",
                (_user_id,),
            )
            cat_row = cur.fetchone()
            assert cat_row is not None
            cat_id = str(cat_row[0])

            # Create an unverified transaction (is_verified=False by default)
            cur.execute(
                "INSERT INTO transactions"
                " (user_id, account_id, category_id, type, amount, currency, balance_delta, date, is_verified)"
                " VALUES (%s, %s, %s, 'expense', 250, 'EGP', -250, NOW(), false) RETURNING id",
                (_user_id, _account_id, cat_id),
            )
        conn.commit()


@pytest.fixture(autouse=True)
def auth(db: None, page: Page) -> None:
    ensure_auth(page)


class TestReconciliation:
    def test_reconcile_page_loads(self, page: Page) -> None:
        """GET /accounts/<id>/reconcile renders the reconcile page."""
        page.goto(f"/accounts/{_account_id}/reconcile")
        expect(page.locator("main")).to_contain_text("Reconcile Account")
        expect(page.locator("#bank-balance")).to_be_visible()

    def test_unverified_transactions_are_listed(self, page: Page) -> None:
        """Unverified transactions appear in the reconcile checklist."""
        page.goto(f"/accounts/{_account_id}/reconcile")
        expect(page.locator('input[name="verified_tx_ids"]')).to_have_count(1)

    def test_balance_input_shows_current_balance(self, page: Page) -> None:
        """The current balance is displayed on the reconcile page."""
        page.goto(f"/accounts/{_account_id}/reconcile")
        expect(page.locator("main")).to_contain_text("Current Balance")

    def test_select_all_enables_submit_button(self, page: Page) -> None:
        """Clicking 'Select All' enables the submit button."""
        page.goto(f"/accounts/{_account_id}/reconcile")
        submit_btn = page.locator("#submit-btn")
        # Initially disabled
        expect(submit_btn).to_be_disabled()
        # Click 'Select All'
        page.click("button:has-text('Select All')")
        # Selected count should be 1
        expect(page.locator("#selected-count")).to_have_text("1")
        # Button should now be enabled
        expect(submit_btn).to_be_enabled()

    def test_complete_reconciliation_redirects_to_account_detail(
        self, page: Page
    ) -> None:
        """Submitting reconciliation redirects to the account detail page."""
        page.goto(f"/accounts/{_account_id}/reconcile")
        # Select all transactions
        page.click("button:has-text('Select All')")
        expect(page.locator("#submit-btn")).to_be_enabled()
        # Submit and wait for redirect
        with page.expect_navigation():
            page.click("#submit-btn")
        # Should land on the account detail page
        expect(page).to_have_url(f"/accounts/{_account_id}", timeout=5000)

    def test_empty_reconcile_shows_no_transactions_message(self, page: Page) -> None:
        """If all transactions are already verified, reconcile shows empty state."""
        # Mark the transaction as verified
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE transactions SET is_verified = true"
                    " WHERE user_id = %s AND account_id = %s",
                    (_user_id, _account_id),
                )
            conn.commit()

        page.goto(f"/accounts/{_account_id}/reconcile")
        expect(page.locator("main")).to_contain_text("No unverified transactions")
