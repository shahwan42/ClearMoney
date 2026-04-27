"""Virtual account (envelope budgeting) tests.

Converts: 14-virtual-accounts.spec.ts

UI notes:
- Create form: regular POST on /virtual-accounts, button text "Create"
- Archive: regular POST form on list page, button text "Archive" (no dialog)
- Detail link: <a> with VA name text
- Detail page: "Allocate Funds" section (regular POST form), "History" section
- Allocate: select[name="type"] with values "contribution"/"withdrawal"
- Edit button on detail page: onclick="openEditVirtualAccount()" → loads form into
  bottom sheet #edit-virtual-account-content via HTMX
- Empty state: "No pots yet. Create one above!"
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


def _create_virtual_account(page: Page, account_id: str, name: str = "Emergency Fund",
                            target_amount: str = "50000") -> None:
    """Create a virtual account via the UI."""
    page.goto("/virtual-accounts")
    page.fill('input[name="name"]', name)
    page.fill('input[name="target_amount"]', target_amount)
    page.select_option('select[name="account_id"]', account_id)
    with page.expect_response(
        lambda r: "/virtual-accounts" in r.url and r.request.method == "POST"
    ):
        page.click('button[type="submit"]')


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


class TestVirtualAccounts:
    def test_empty_state(self, page: Page) -> None:
        page.goto("/virtual-accounts")
        expect(page.locator("main")).to_contain_text("No pots yet")

    def test_create_virtual_account(self, page: Page) -> None:
        page.goto("/virtual-accounts")
        page.fill('input[name="name"]', "Emergency Fund")
        page.fill('input[name="target_amount"]', "50000")
        page.select_option('select[name="account_id"]', _account_id)
        with page.expect_response(
            lambda r: "/virtual-accounts" in r.url and r.request.method == "POST"
        ):
            page.click('button[type="submit"]')
        expect(page.locator("main")).to_contain_text("Emergency Fund")

    def test_linked_usd_account_uses_inherited_currency(self, page: Page) -> None:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO institutions (user_id, name, type, display_order)"
                    " VALUES (%s, 'USD Bank', 'bank', 1) RETURNING id",
                    (_user_id,),
                )
                usd_inst_id = str(cur.fetchone()[0])  # type: ignore[index]
                cur.execute(
                    "INSERT INTO accounts"
                    " (user_id, institution_id, name, type, currency, current_balance, initial_balance, display_order)"
                    " VALUES (%s, %s, 'USD Current', 'current', 'USD', 500, 500, 1) RETURNING id",
                    (_user_id, usd_inst_id),
                )
                usd_account_id = str(cur.fetchone()[0])  # type: ignore[index]
            conn.commit()

        _create_virtual_account(
            page,
            usd_account_id,
            name="USD Goal",
            target_amount="250",
        )

        expect(page.locator("main")).to_contain_text("USD Goal")
        expect(page.locator("main")).to_contain_text("$0.00")
        page.click('a:has-text("USD Goal")')
        expect(page.locator("main")).to_contain_text("$0.00")
        expect(page.locator("main")).to_contain_text("$250.00")

    def test_detail_page_shows_sections(self, page: Page) -> None:
        _create_virtual_account(page, _account_id)
        page.goto("/virtual-accounts")
        page.click('a:has-text("Emergency Fund")')
        expect(page.locator("main")).to_contain_text("Allocate Funds")
        expect(page.locator("main")).to_contain_text("History")

    def test_allocate_funds(self, page: Page) -> None:
        _create_virtual_account(page, _account_id)
        page.goto("/virtual-accounts")
        page.click('a:has-text("Emergency Fund")')
        page.select_option('select[name="type"]', "contribution")
        page.fill('input[name="amount"]', "5000")
        page.fill('input[name="note"]', "First deposit")
        page.click('button:has-text("Allocate")')
        page.wait_for_load_state()
        expect(page.locator("main")).to_contain_text("5,000")

    def test_edit_via_bottom_sheet(self, page: Page) -> None:
        _create_virtual_account(page, _account_id)
        page.goto("/virtual-accounts")
        page.click('a:has-text("Emergency Fund")')
        # Edit button opens bottom sheet via openEditVirtualAccount() → HTMX loads edit form
        page.click('button:has-text("Edit")')
        edit_content = page.locator("#edit-virtual-account-content")
        name_input = edit_content.locator('input[name="name"]')
        name_input.wait_for(state="visible")
        name_input.fill("Rainy Day Fund")
        with page.expect_response(
            lambda r: "virtual-accounts" in r.url and r.request.method == "POST"
        ):
            edit_content.locator('button[type="submit"]').click()
        expect(page.locator("main")).to_contain_text("Rainy Day Fund")

    def test_archive_virtual_account(self, page: Page) -> None:
        _create_virtual_account(page, _account_id)
        page.goto("/virtual-accounts")
        # Archive button is on the list page (regular POST form, no dialog)
        with page.expect_response(
            lambda r: "archive" in r.url and r.request.method == "POST"
        ):
            page.click('button:has-text("Archive")')
        expect(page.locator("main")).to_contain_text("No pots yet")

    @pytest.mark.timeout(90)
    def test_auto_allocate_from_recurring_income(self, page: Page) -> None:
        """E2E test for enabling auto-allocate → confirming recurring → VA balance updated."""
        from conftest import get_category_id
        category_id = get_category_id("income", _user_id)
        
        # 1. Create a virtual account with auto_allocate
        page.goto("/virtual-accounts")
        page.fill('input[name="name"]', "Project Savings")
        page.fill('input[name="target_amount"]', "10000")
        page.fill('input[name="monthly_target"]', "500")
        page.select_option('select[name="account_id"]', _account_id)
        page.check('input[name="auto_allocate"]')
        with page.expect_response(
            lambda r: "/virtual-accounts" in r.url and r.request.method == "POST"
        ):
            page.click('button[type="submit"]')
            
        # 2. Go to recurring and create income rule (form is in bottom sheet)
        page.goto("/recurring")
        page.click('button:has-text("+ Automation")')
        page.wait_for_selector("#rec-form", timeout=5000)
        page.click('input[name="type"][value="income"]', force=True)
        page.fill("#rec-amount", "2000")
        page.evaluate(
            f"document.getElementById('rec-account-combobox')._accountCombobox.selectById('{_account_id}')"
        )
        page.evaluate(
            f"document.getElementById('rec-category-combobox')._combobox.selectById('{category_id}')"
        )
        page.fill("#rec-note-input", "Salary")
        page.select_option("#rec-frequency", "monthly")
        page.fill("#rec-next-due", "2026-04-01")
        with page.expect_response(
            lambda r: "/recurring/add" in r.url and r.request.method == "POST"
        ):
            page.click('button:has-text("Create Rule")')

        # 3. Navigate to recurring page fresh (sheet closed) to see the pending rule section
        page.goto("/recurring")

        # Open the confirm form sheet and submit it
        page.click('button:has-text("Confirm")')
        page.wait_for_selector("#recurring-confirm-form", timeout=5000)
        with page.expect_response(lambda r: "confirm" in r.url and r.request.method == "POST"):
            page.click('#recurring-confirm-form button[type="submit"]')
            
        # 4. Check VA balance updated
        page.goto("/virtual-accounts")
        # Check that VA has 500 allocated
        page.click('a:has-text("Project Savings")')
        expect(page.locator("main")).to_contain_text("500")
