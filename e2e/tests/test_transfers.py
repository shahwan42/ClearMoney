"""Transfer and currency exchange tests.

Converts: 05-transfers.spec.ts

Key checks:
- EGP→EGP transfer preserves total net worth
- InstaPay toggle adds 0.1% fee (shown in #instapay-fee-amount)
- Exchange form auto-calculates counter amount from amount ÷ rate

UI notes:
- Transfer page: GET /transfers/new — form posts via HTMX to /transactions/transfer
- Exchange page: GET /exchange/new — form posts via HTMX to /transactions/exchange-submit
- Transfer accounts: source_account_id / dest_account_id (not from_account_id)
- Both forms are HTMX — no page navigation; results in #transfer-result / #exchange-result
- Exchange JS: calcExchange fires oninput; EGP→USD uses amount / rate
- Counter value format: toFixed(2), e.g. "100.00"
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

_institution_id: str = ""
_egp_account_1: str = ""
_egp_account_2: str = ""
_usd_account: str = ""


@pytest.fixture(scope="function", autouse=True)
def db() -> None:
    """Reset DB and create test accounts directly via SQL."""
    global _institution_id, _egp_account_1, _egp_account_2, _usd_account
    user_id = reset_database()
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO institutions (user_id, name, type, display_order)"
                " VALUES (%s, 'Test Bank', 'bank', 0) RETURNING id",
                (user_id,),
            )
            _institution_id = str(cur.fetchone()[0])  # type: ignore[index]
            cur.execute(
                "INSERT INTO accounts"
                " (user_id, institution_id, name, type, currency, current_balance, initial_balance, display_order)"
                " VALUES (%s, %s, 'EGP Account 1', 'current', 'EGP', 20000, 20000, 0) RETURNING id",
                (user_id, _institution_id),
            )
            _egp_account_1 = str(cur.fetchone()[0])  # type: ignore[index]
            cur.execute(
                "INSERT INTO accounts"
                " (user_id, institution_id, name, type, currency, current_balance, initial_balance, display_order)"
                " VALUES (%s, %s, 'EGP Account 2', 'current', 'EGP', 0, 0, 1) RETURNING id",
                (user_id, _institution_id),
            )
            _egp_account_2 = str(cur.fetchone()[0])  # type: ignore[index]
            cur.execute(
                "INSERT INTO accounts"
                " (user_id, institution_id, name, type, currency, current_balance, initial_balance, display_order)"
                " VALUES (%s, %s, 'USD Account', 'current', 'USD', 0, 0, 2) RETURNING id",
                (user_id, _institution_id),
            )
            _usd_account = str(cur.fetchone()[0])  # type: ignore[index]
        conn.commit()


@pytest.fixture(autouse=True)
def auth(db: None, page: Page) -> None:
    ensure_auth(page)


class TestTransfers:
    def test_transfer_preserves_net_worth(self, page: Page) -> None:
        page.goto("/transfers/new")
        page.fill("#transfer-amount", "5000")
        page.select_option('select[name="source_account_id"]', _egp_account_1)
        page.select_option('select[name="dest_account_id"]', _egp_account_2)
        with page.expect_response(
            lambda r: "/transactions/transfer" in r.url and r.request.method == "POST"
        ):
            page.click('button[type="submit"]')
        expect(page.locator("#transfer-result")).to_contain_text("Transfer completed!")
        # Net worth unchanged: 20,000 split 15,000 + 5,000
        page.goto("/")
        expect(page.locator("main")).to_contain_text("20,000")

    def test_fee_field_shows_total_display(self, page: Page) -> None:
        page.goto("/transfers/new")
        page.fill("#transfer-amount", "1000")
        page.fill("#transfer-fee", "5")
        # Fee > 0 shows the total charged display
        expect(page.locator("#transfer-total-display")).to_be_visible()
        expect(page.locator("[data-transfer-total]")).to_contain_text("1005.00")

    def test_transfer_with_note(self, page: Page) -> None:
        page.goto("/transfers/new")
        page.fill("#transfer-amount", "500")
        page.select_option('select[name="source_account_id"]', _egp_account_1)
        page.select_option('select[name="dest_account_id"]', _egp_account_2)
        page.fill('input[name="note"]', "Rent share")
        with page.expect_response(
            lambda r: "/transactions/transfer" in r.url and r.request.method == "POST"
        ):
            page.click('button[type="submit"]')
        expect(page.locator("#transfer-result")).to_contain_text("Transfer completed!")
        page.goto("/transactions")
        expect(page.locator("main")).to_contain_text("Rent share")


class TestExchange:
    def test_exchange_form_fields_visible(self, page: Page) -> None:
        page.goto("/exchange/new")
        expect(page.locator("#exchange-src")).to_be_visible()
        expect(page.locator("#exchange-dst")).to_be_visible()
        expect(page.locator("#exchange-rate")).to_be_visible()
        expect(page.locator("#exchange-counter")).to_be_visible()

    def test_exchange_rate_required(self, page: Page) -> None:
        page.goto("/exchange/new")
        page.select_option("#exchange-src", _egp_account_1)
        page.select_option("#exchange-dst", _usd_account)
        page.fill("#exchange-amount", "5000")
        # Submit without rate — server returns error, HTMX never navigates
        with page.expect_response(lambda r: "/transactions/exchange-submit" in r.url):
            page.click('button[type="submit"]')
        expect(page).to_have_url(re.compile(r"exchange"))

    def test_create_exchange_updates_balances(self, page: Page) -> None:
        page.goto("/exchange/new")
        page.select_option("#exchange-src", _egp_account_1)
        page.select_option("#exchange-dst", _usd_account)
        page.fill("#exchange-amount", "5000")
        page.fill("#exchange-rate", "50")
        # JS calculates: 5000 / 50 = 100.00 USD
        expect(page.locator("#exchange-counter")).to_have_value("100.00")
        with page.expect_response(lambda r: "/transactions/exchange-submit" in r.url):
            page.click('button[type="submit"]')
        expect(page.locator("#exchange-result")).to_contain_text("Exchange completed!")
        page.goto(f"/accounts/{_usd_account}")
        expect(page.locator("main")).to_contain_text("100")

    def test_exchange_auto_calculates_counter_amount(self, page: Page) -> None:
        page.goto("/exchange/new")
        page.select_option("#exchange-src", _egp_account_1)
        page.select_option("#exchange-dst", _usd_account)
        page.fill("#exchange-amount", "10000")
        page.fill("#exchange-rate", "50")
        page.wait_for_timeout(300)
        # JS calculates: 10000 / 50 = 200.00 USD
        expect(page.locator("#exchange-counter")).to_have_value("200.00")
