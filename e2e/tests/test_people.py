"""People and loan tracking tests.

Converts: 06-people.spec.ts

UI notes:
- Add person: form on page with input[name="name"], button text "Add"
- Loan form: hidden, toggled by "Record Loan" button (onclick=toggleLoanForm)
- Repay form: hidden, toggled by "Repayment" button (only shown when balance != 0)
- Loan HTMX: hx-post="/people/{id}/loan", target="#people-list"
- Repay HTMX: hx-post="/people/{id}/repay", target="#people-list"
- No category_id in loan/repay forms
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


def _add_person(page: Page, name: str = "Ahmed") -> None:
    """Add a person via the UI."""
    page.goto("/people")
    page.fill('input[name="name"]', name)
    with page.expect_response(
        lambda r: "/people/add" in r.url and r.request.method == "POST"
    ):
        page.click('button[type="submit"]')


def _record_loan(page: Page, amount: str = "500") -> None:
    """Record a loan for the first person."""
    page.goto("/people")
    page.click('button:has-text("Record Loan")')
    loan_form = page.locator('[id^="loan-form-"]').first
    loan_form.locator('input[name="amount"]').fill(amount)
    loan_form.locator('select[name="account_id"]').select_option(_account_id)
    with page.expect_response(
        lambda r: "/loan" in r.url and r.request.method == "POST"
    ):
        loan_form.locator('button[type="submit"]').click()


class TestPeople:
    def test_people_page_empty_state(self, page: Page) -> None:
        page.goto("/people")
        expect(page.locator("main")).to_contain_text("No people yet")

    def test_add_person(self, page: Page) -> None:
        page.goto("/people")
        page.fill('input[name="name"]', "Ahmed")
        with page.expect_response(
            lambda r: "/people/add" in r.url and r.request.method == "POST"
        ):
            page.click('button[type="submit"]')
        expect(page.locator("main")).to_contain_text("Ahmed")

    def test_record_loan_i_lent(self, page: Page) -> None:
        _add_person(page)
        page.goto("/people")
        # Click "Record Loan" to toggle the hidden loan form
        page.click('button:has-text("Record Loan")')
        loan_form = page.locator('[id^="loan-form-"]').first
        loan_form.locator('input[name="amount"]').fill("500")
        loan_form.locator('select[name="account_id"]').select_option(_account_id)
        with page.expect_response(
            lambda r: "/loan" in r.url and r.request.method == "POST"
        ):
            loan_form.locator('button[type="submit"]').click()
        expect(page.locator("main")).to_contain_text("500")

    def test_record_repayment(self, page: Page) -> None:
        _add_person(page)
        _record_loan(page)
        page.goto("/people")
        # "Repayment" button appears when net_balance != 0 (Ahmed owes 500)
        page.click('button:has-text("Repayment")')
        repay_form = page.locator('[id^="repay-form-"]').first
        repay_form.locator('input[name="amount"]').fill("200")
        repay_form.locator('select[name="account_id"]').select_option(_account_id)
        with page.expect_response(
            lambda r: "/repay" in r.url and r.request.method == "POST"
        ):
            repay_form.locator('button[type="submit"]').click()
        # Remaining: 500 - 200 = 300
        expect(page.locator("main")).to_contain_text("300")

    def test_people_summary_on_dashboard(self, page: Page) -> None:
        _add_person(page)
        _record_loan(page)
        page.goto("/people")
        # Record repayment: 500 - 200 = 300
        page.click('button:has-text("Repayment")')
        repay_form = page.locator('[id^="repay-form-"]').first
        repay_form.locator('input[name="amount"]').fill("200")
        repay_form.locator('select[name="account_id"]').select_option(_account_id)
        with page.expect_response(
            lambda r: "/repay" in r.url and r.request.method == "POST"
        ):
            repay_form.locator('button[type="submit"]').click()
        # Navigate to dashboard
        page.goto("/")
        # Dashboard shows aggregate people summary (not individual names)
        # After lending 500 and receiving 200 back, owed_to_me = 300
        expect(page.locator("main")).to_contain_text("People")
        expect(page.locator("main")).to_contain_text("300")
