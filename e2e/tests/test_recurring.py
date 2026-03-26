"""Recurring transaction rule tests.

Converts: 07-recurring.spec.ts

UI notes:
- Form fields: type (sr-only peer radio, defaults to expense), amount, account_id,
  category_id, note (NOT description), frequency, next_due_date
- Form HTMX: hx-post="/recurring/add", target="#recurring-list"
- Delete button: text "Del", hx-delete, hx-confirm fires browser confirm dialog
- List shows note text and frequency value (e.g., "monthly")
- Empty state: "No recurring rules yet."
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
def auth(db: None, page: Page) -> None:
    ensure_auth(page)


def _create_recurring_rule(page: Page, note: str = "Netflix", amount: str = "200", frequency: str = "monthly") -> None:
    """Create a recurring rule via the UI."""
    category_id = get_category_id("expense", _user_id)
    page.goto("/recurring")
    page.fill('input[name="amount"]', amount)
    page.select_option('select[name="account_id"]', _account_id)
    page.evaluate(
        f"document.querySelector('[data-category-combobox]')._combobox.selectById('{category_id}')"
    )
    page.fill('input[name="note"]', note)
    page.select_option('select[name="frequency"]', frequency)
    page.fill('input[name="next_due_date"]', "2026-04-01")
    with page.expect_response(
        lambda r: "/recurring/add" in r.url and r.request.method == "POST"
    ):
        page.click('button[type="submit"]')


class TestRecurring:
    def test_create_recurring_rule(self, page: Page) -> None:
        category_id = get_category_id("expense", _user_id)
        page.goto("/recurring")
        # Type defaults to "expense" — no need to change the hidden radio
        page.fill('input[name="amount"]', "200")
        page.select_option('select[name="account_id"]', _account_id)
        # Category uses a custom combobox — select via its programmatic API
        page.evaluate(
            f"document.querySelector('[data-category-combobox]')._combobox.selectById('{category_id}')"
        )
        page.fill('input[name="note"]', "Netflix")
        page.select_option('select[name="frequency"]', "monthly")
        page.fill('input[name="next_due_date"]', "2026-04-01")
        with page.expect_response(
            lambda r: "/recurring/add" in r.url and r.request.method == "POST"
        ):
            page.click('button[type="submit"]')
        expect(page.locator("#recurring-list")).to_contain_text("Netflix")

    def test_recurring_list_shows_frequency(self, page: Page) -> None:
        _create_recurring_rule(page)
        # List should already have Netflix from the helper, but verify it's there
        expect(page.locator("#recurring-list")).to_contain_text("Netflix")
        expect(page.locator("#recurring-list")).to_contain_text("monthly")

    def test_delete_recurring_rule(self, page: Page) -> None:
        _create_recurring_rule(page)
        # Verify rule exists before deleting
        expect(page.locator("#recurring-list")).to_contain_text("Netflix")
        # Register dialog handler before clicking — hx-confirm fires browser confirm()
        page.on("dialog", lambda d: d.accept())
        with page.expect_response(
            lambda r: "/recurring/" in r.url and r.request.method == "DELETE"
        ):
            page.click('button:has-text("Del")')
        expect(page.locator("#recurring-list")).not_to_contain_text("Netflix")
