"""Transaction CRUD, filtering, and search tests.

Converts: 03-transactions.spec.ts

Balance flow: initial 10,000 → expense -150 → income +5,000 = 14,850

UI notes:
- Transaction type: radio buttons (input[name="type"]), NOT a select
- Form: HTMX-based, posts to /transactions, result rendered in #transaction-result
- Success template: shows "Transaction saved!" in bg-teal-50 div
- Search input: name="search" (id="search-input"), 300ms debounce via keyup/change
- Type filter: select[name="type"] triggers HTMX immediately (no debounce)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from playwright.sync_api import Page, expect
from conftest import (
    _conn,
    create_transaction,
    ensure_auth,
    get_category_id,
    reset_database,
)

_account_id: str = ""
_user_id: str = ""


@pytest.fixture(scope="function", autouse=True)
def db() -> None:
    """Reset DB and create test institution + account directly via SQL."""
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
                " VALUES (%s, %s, 'Current', 'current', 'EGP', 10000, 10000, 0) RETURNING id",
                (_user_id, inst_id),
            )
            _account_id = str(cur.fetchone()[0])  # type: ignore[index]
        conn.commit()


@pytest.fixture(autouse=True)
def auth(page: Page) -> None:
    ensure_auth(page)


class TestTransactionCRUD:
    def test_transaction_form_shows_account_dropdown(self, page: Page) -> None:
        page.goto("/transactions/new")
        expect(page.locator('select[name="account_id"]')).to_be_visible()
        expect(page.locator('select[name="account_id"]')).to_contain_text("Current")

    def test_create_expense_updates_balance(self, page: Page) -> None:
        category_id = get_category_id("expense", _user_id)
        page.goto("/transactions/new")
        page.select_option('select[name="account_id"]', _account_id)
        # Type uses hidden radios (Tailwind peer pattern) — click the visible label div
        page.click('#type-expense-label')
        # Category uses a custom combobox — select via its programmatic API
        page.evaluate(
            f"document.querySelector('[data-category-combobox]')._combobox.selectById('{category_id}')"
        )
        page.fill('input[name="amount"]', "150")
        page.fill('input[name="note"]', "Coffee")

        with page.expect_response(
            lambda r: "/transactions" in r.url and r.request.method == "POST"
        ):
            page.click('button[type="submit"]')

        expect(page.locator("#transaction-result")).to_contain_text("Transaction saved!")
        # 10,000 - 150 = 9,850
        page.goto(f"/accounts/{_account_id}")
        expect(page.locator("main")).to_contain_text("9,850")

    def test_create_income_updates_balance(self, page: Page) -> None:
        category_id = get_category_id("income", _user_id)
        page.goto("/transactions/new")
        page.select_option('select[name="account_id"]', _account_id)
        page.click('#type-income-label')
        # Category uses a custom combobox — select via its programmatic API
        page.evaluate(
            f"document.querySelector('[data-category-combobox]')._combobox.selectById('{category_id}')"
        )
        page.fill('input[name="amount"]', "5000")
        page.fill('input[name="note"]', "Salary")

        with page.expect_response(
            lambda r: "/transactions" in r.url and r.request.method == "POST"
        ):
            page.click('button[type="submit"]')

        expect(page.locator("#transaction-result")).to_contain_text("Transaction saved!")
        # 9,850 + 5,000 = 14,850
        page.goto(f"/accounts/{_account_id}")
        expect(page.locator("main")).to_contain_text("14,850")

    def test_transactions_list_shows_all_transactions(self, page: Page) -> None:
        page.goto("/transactions")
        expect(page.locator("main")).to_contain_text("Coffee")
        expect(page.locator("main")).to_contain_text("Salary")

    def test_filter_by_type_shows_only_expenses(self, page: Page) -> None:
        page.goto("/transactions")
        with page.expect_response(lambda r: "/transactions/list" in r.url):
            page.select_option('select[name="type"]', "expense")
        # Scope to #transaction-list — the filter form also has "Salary" in income categories
        tx_list = page.locator("#transaction-list")
        expect(tx_list).to_contain_text("Coffee")
        expect(tx_list).not_to_contain_text("Salary")  # Salary is the income note

    def test_search_by_note_with_debounce(self, page: Page) -> None:
        page.goto("/transactions")
        # Use keyboard.type() to fire keyup events (needed for 300ms debounce trigger)
        with page.expect_response(lambda r: "/transactions/list" in r.url):
            page.locator("#search-input").click()
            page.keyboard.type("Coffee")
            page.wait_for_timeout(400)  # wait for 300ms debounce to fire
        tx_list = page.locator("#transaction-list")
        expect(tx_list).to_contain_text("Coffee")
        expect(tx_list).not_to_contain_text("Salary")

    def test_dashboard_shows_recent_transactions(self, page: Page) -> None:
        page.goto("/")
        expect(page.locator("main")).to_contain_text("Coffee")

    def test_delete_transaction_via_api(self, page: Page) -> None:
        category_id = get_category_id("expense", _user_id)
        tx_id = create_transaction(
            page, _account_id, category_id, "99", "expense", note="DeleteMe"
        )
        page.goto("/transactions")
        expect(page.locator("main")).to_contain_text("DeleteMe")

        resp = page.request.delete(f"/api/transactions/{tx_id}")
        assert resp.ok

        page.reload()
        expect(page.locator("main")).not_to_contain_text("DeleteMe")
