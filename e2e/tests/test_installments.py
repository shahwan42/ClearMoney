"""Installment plan (EMI) tests.

Converts: 09-installments.spec.ts

UI notes:
- Create form: hx-post="/installments/add", fields: description, total_amount,
  num_installments, account_id, start_date. Button: "Create Plan"
- Pay button: "Record Payment" with hx-confirm dialog
- Delete button: "Del" with hx-confirm dialog
- Empty state: "No installment plans yet."
- Uses a credit card account as the payment source.
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

_cc_account_id: str = ""
_user_id: str = ""


@pytest.fixture(scope="module", autouse=True)
def db() -> None:
    """Reset DB and create test institution + credit card account via SQL."""
    global _cc_account_id, _user_id
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
                " (user_id, institution_id, name, type, currency, current_balance,"
                "  initial_balance, credit_limit, display_order)"
                " VALUES (%s, %s, 'CC', 'credit_card', 'EGP', 0, 0, 100000, 0) RETURNING id",
                (_user_id, inst_id),
            )
            _cc_account_id = str(cur.fetchone()[0])  # type: ignore[index]
        conn.commit()


@pytest.fixture(autouse=True)
def auth(page: Page) -> None:
    ensure_auth(page)


class TestInstallments:
    def test_create_installment_plan(self, page: Page) -> None:
        page.goto("/installments")
        page.fill('input[name="description"]', "MacBook Pro")
        page.fill('input[name="total_amount"]', "60000")
        page.fill('input[name="num_installments"]', "12")
        page.select_option('select[name="account_id"]', _cc_account_id)
        page.fill('input[name="start_date"]', "2026-01-01")
        with page.expect_response(
            lambda r: "/installments/add" in r.url and r.request.method == "POST"
        ):
            page.click('button[type="submit"]')
        expect(page.locator("main")).to_contain_text("MacBook Pro")

    def test_installment_plan_shows_schedule(self, page: Page) -> None:
        page.goto("/installments")
        # Plan shows "12 installments" or "0 of 12 paid" etc.
        expect(page.locator("main")).to_contain_text("12")

    def test_record_installment_payment(self, page: Page) -> None:
        page.goto("/installments")
        # "Record Payment" button uses hx-confirm — register dialog handler first
        page.on("dialog", lambda d: d.accept())
        with page.expect_response(
            lambda r: "/pay" in r.url and r.request.method == "POST"
        ):
            page.click('button:has-text("Record Payment")')
        expect(page.locator("main")).to_contain_text("MacBook Pro")

    def test_delete_installment_plan(self, page: Page) -> None:
        page.goto("/installments")
        # "Del" button uses hx-confirm — register dialog handler first
        page.on("dialog", lambda d: d.accept())
        with page.expect_response(
            lambda r: "/installments/" in r.url and r.request.method == "DELETE"
        ):
            page.click('button:has-text("Del")')
        expect(page.locator("main")).to_contain_text("No installment plans yet")
