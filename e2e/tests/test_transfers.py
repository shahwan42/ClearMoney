"""Transfer and currency exchange tests — unified Move Money form.

Key checks:
- EGP→EGP transfer preserves total net worth
- Fee field shows total display when fee > 0
- Exchange form auto-calculates counter amount from amount ÷ rate
- Mode auto-detects based on selected account currencies

UI notes:
- Move Money page: GET /move-money/new — auto-detects transfer vs exchange
- Transfer mode: posts via HTMX to /transactions/transfer
- Exchange mode: posts via HTMX to /transactions/exchange-submit
- Account selects: source_account_id / dest_account_id with data-currency
- Results replace #move-money-content
- Exchange JS: calcMoveExchange fires oninput; EGP→USD uses amount / rate
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
        page.goto("/move-money/new")
        # Select same-currency accounts to trigger transfer mode
        page.select_option("#move-src", _egp_account_1)
        page.select_option("#move-dst", _egp_account_2)
        page.fill("#move-amount", "5000")
        with page.expect_response(
            lambda r: "/transactions/transfer" in r.url and r.request.method == "POST"
        ):
            page.click('button[type="submit"]')
        expect(page.locator("#move-money-content")).to_contain_text(
            "Transfer completed!"
        )
        page.goto("/")
        expect(page.locator("main")).to_contain_text("20,000")

    def test_fee_field_shows_total_display(self, page: Page) -> None:
        page.goto("/move-money/new")
        # Select same-currency accounts to show fee field
        page.select_option("#move-src", _egp_account_1)
        page.select_option("#move-dst", _egp_account_2)
        page.fill("#move-amount", "1000")
        page.fill("#move-fee", "5")
        # Fee > 0 shows the total charged display
        expect(page.locator("#move-total-display")).to_be_visible()
        expect(page.locator("#move-total-value")).to_contain_text("1005.00")

    def test_transfer_with_note(self, page: Page) -> None:
        page.goto("/move-money/new")
        page.select_option("#move-src", _egp_account_1)
        page.select_option("#move-dst", _egp_account_2)
        page.fill("#move-amount", "500")
        page.fill('input[name="note"]', "Rent share")
        with page.expect_response(
            lambda r: "/transactions/transfer" in r.url and r.request.method == "POST"
        ):
            page.click('button[type="submit"]')
        expect(page.locator("#move-money-content")).to_contain_text(
            "Transfer completed!"
        )
        page.goto("/transactions")
        expect(page.locator("main")).to_contain_text("Rent share")

    def test_old_transfer_url_redirects(self, page: Page) -> None:
        page.goto("/transfers/new")
        expect(page).to_have_url(re.compile(r"move-money/new"))


class TestExchange:
    def test_exchange_fields_visible_for_different_currencies(self, page: Page) -> None:
        page.goto("/move-money/new")
        # Select different-currency accounts to trigger exchange mode
        page.select_option("#move-src", _egp_account_1)
        page.select_option("#move-dst", _usd_account)
        expect(page.locator("#move-exchange-fields")).to_be_visible()
        expect(page.locator("#move-rate")).to_be_visible()
        expect(page.locator("#move-counter")).to_be_visible()

    def test_exchange_rate_required(self, page: Page) -> None:
        page.goto("/move-money/new")
        page.select_option("#move-src", _egp_account_1)
        page.select_option("#move-dst", _usd_account)
        page.fill("#move-amount", "5000")
        # Submit without rate — server returns error, HTMX never navigates
        with page.expect_response(lambda r: "/transactions/exchange-submit" in r.url):
            page.click('button[type="submit"]')
        expect(page).to_have_url(re.compile(r"move-money"))

    def test_create_exchange_updates_balances(self, page: Page) -> None:
        page.goto("/move-money/new")
        page.select_option("#move-src", _egp_account_1)
        page.select_option("#move-dst", _usd_account)
        page.fill("#move-amount", "5000")
        page.fill("#move-rate", "50")
        # JS calculates: 5000 / 50 = 100.00 USD
        expect(page.locator("#move-counter")).to_have_value("100.00")
        with page.expect_response(lambda r: "/transactions/exchange-submit" in r.url):
            page.click('button[type="submit"]')
        expect(page.locator("#move-money-content")).to_contain_text(
            "Exchange completed!"
        )
        page.goto(f"/accounts/{_usd_account}")
        expect(page.locator("main")).to_contain_text("100")

    def test_exchange_auto_calculates_counter_amount(self, page: Page) -> None:
        page.goto("/move-money/new")
        page.select_option("#move-src", _egp_account_1)
        page.select_option("#move-dst", _usd_account)
        page.fill("#move-amount", "10000")
        page.fill("#move-rate", "50")
        page.wait_for_timeout(300)
        # JS calculates: 10000 / 50 = 200.00 USD
        expect(page.locator("#move-counter")).to_have_value("200.00")

    def test_old_exchange_url_redirects(self, page: Page) -> None:
        page.goto("/exchange/new")
        expect(page).to_have_url(re.compile(r"move-money/new"))


class TestMoveMoneyModeDetection:
    def test_transfer_mode_for_same_currency(self, page: Page) -> None:
        page.goto("/move-money/new")
        page.select_option("#move-src", _egp_account_1)
        page.select_option("#move-dst", _egp_account_2)
        # Transfer fields visible, exchange fields hidden
        expect(page.locator("#move-transfer-fields")).to_be_visible()
        expect(page.locator("#move-exchange-fields")).not_to_be_visible()
        expect(page.locator("#move-mode-indicator")).to_contain_text("transfer")

    def test_exchange_mode_for_different_currencies(self, page: Page) -> None:
        page.goto("/move-money/new")
        page.select_option("#move-src", _egp_account_1)
        page.select_option("#move-dst", _usd_account)
        # Exchange fields visible, transfer fields hidden
        expect(page.locator("#move-exchange-fields")).to_be_visible()
        expect(page.locator("#move-transfer-fields")).not_to_be_visible()
        expect(page.locator("#move-mode-indicator")).to_contain_text("exchange")

    def test_mode_switches_dynamically(self, page: Page) -> None:
        page.goto("/move-money/new")
        # Start with same currency (transfer mode)
        page.select_option("#move-src", _egp_account_1)
        page.select_option("#move-dst", _egp_account_2)
        expect(page.locator("#move-transfer-fields")).to_be_visible()
        # Switch to different currency (exchange mode)
        page.select_option("#move-dst", _usd_account)
        expect(page.locator("#move-exchange-fields")).to_be_visible()
        expect(page.locator("#move-transfer-fields")).not_to_be_visible()
