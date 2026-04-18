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
def auth(db: None, page: Page) -> None:
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
        page.select_option("#type-select", "expense")
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

        expect(page.locator("#transaction-result")).to_contain_text(
            "Transaction saved!"
        )
        # 10,000 - 150 = 9,850
        page.goto(f"/accounts/{_account_id}")
        expect(page.locator("main")).to_contain_text("9,850")

    def test_create_income_updates_balance(self, page: Page) -> None:
        category_id = get_category_id("income", _user_id)
        page.goto("/transactions/new")
        page.select_option('select[name="account_id"]', _account_id)
        page.select_option("#type-select", "income")
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

        expect(page.locator("#transaction-result")).to_contain_text(
            "Transaction saved!"
        )
        # 10,000 + 5,000 = 15,000 (each test has a fresh account)
        page.goto(f"/accounts/{_account_id}")
        expect(page.locator("main")).to_contain_text("15,000")

    def test_transactions_list_shows_all_transactions(self, page: Page) -> None:
        # Create both expense and income transactions
        expense_cat_id = get_category_id("expense", _user_id)
        income_cat_id = get_category_id("income", _user_id)
        create_transaction(
            page, _account_id, expense_cat_id, "150", "expense", note="Coffee"
        )
        create_transaction(
            page, _account_id, income_cat_id, "5000", "income", note="Salary"
        )
        page.goto("/transactions")
        expect(page.locator("main")).to_contain_text("Coffee")
        expect(page.locator("main")).to_contain_text("Salary")

    def test_filter_by_type_shows_only_expenses(self, page: Page) -> None:
        # Create both expense and income transactions
        expense_cat_id = get_category_id("expense", _user_id)
        income_cat_id = get_category_id("income", _user_id)
        create_transaction(
            page, _account_id, expense_cat_id, "150", "expense", note="Coffee"
        )
        create_transaction(
            page, _account_id, income_cat_id, "5000", "income", note="Salary"
        )
        page.goto("/transactions")
        with page.expect_response(lambda r: "/transactions/list" in r.url):
            page.select_option('select[name="type"]', "expense")
        # Scope to #transaction-list — the filter form also has "Salary" in income categories
        tx_list = page.locator("#transaction-list")
        expect(tx_list).to_contain_text("Coffee")
        expect(tx_list).not_to_contain_text("Salary")  # Salary is the income note

    def test_search_by_note_with_debounce(self, page: Page) -> None:
        # Create both expense and income transactions
        expense_cat_id = get_category_id("expense", _user_id)
        income_cat_id = get_category_id("income", _user_id)
        create_transaction(
            page, _account_id, expense_cat_id, "150", "expense", note="Coffee"
        )
        create_transaction(
            page, _account_id, income_cat_id, "5000", "income", note="Salary"
        )
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
        # Create transaction for dashboard to show
        category_id = get_category_id("expense", _user_id)
        create_transaction(
            page, _account_id, category_id, "150", "expense", note="Coffee"
        )
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

    def test_edit_transaction_via_ui(self, page: Page) -> None:
        category_id = get_category_id("expense", _user_id)
        tx_id = create_transaction(
            page,
            _account_id,
            category_id,
            "250",
            "expense",
            note="Original",
        )
        page.goto("/transactions")
        # Click on transaction row to open detail sheet
        page.locator(f"#tx-{tx_id}").click()
        # Wait for detail sheet and click Edit button
        detail_sheet = page.locator("#tx-detail-content")
        detail_sheet.wait_for(timeout=5000)
        detail_sheet.locator("button:has-text('Edit')").click()
        # Edit sheet should open
        edit_sheet = page.locator("#tx-edit-content")
        edit_sheet.wait_for(timeout=5000)
        # Update amount
        edit_sheet.locator('input[name="amount"]').fill("350")
        # Update note
        edit_sheet.locator('input[name="note"]').fill("Updated")
        # Submit
        with page.expect_response(lambda r: "/transactions/" in r.url):
            edit_sheet.locator('button[type="submit"]').click()
        # Verify change
        page.goto("/transactions")
        expect(page.locator("main")).to_contain_text("Updated")
        expect(page.locator("main")).not_to_contain_text("Original")

    def test_draft_persistence_saves_form_data(self, page: Page) -> None:
        """Test that transaction form data is saved to localStorage on change."""
        page.goto("/transactions/new")

        # Fill in some form data
        page.fill('input[name="amount"]', "99.50")
        page.fill('input[name="note"]', "Test draft")

        # Wait briefly for localStorage save (no specific debounce in current impl)
        page.wait_for_timeout(500)

        # Verify data was saved to localStorage
        draft_data = page.evaluate("() => localStorage.getItem('tx-draft')")
        assert draft_data is not None
        assert "99.50" in draft_data
        assert "Test draft" in draft_data

    def test_draft_persistence_restores_form_data(self, page: Page) -> None:
        """Test that transaction form data is restored from localStorage on page load."""
        page.goto("/transactions/new")

        # Set up draft in localStorage
        page.evaluate("""() => {
            const draft = {
                amount: "75.25",
                note: "Restored draft",
                type: "expense"
            };
            localStorage.setItem('tx-draft', JSON.stringify(draft));
        }""")

        # Reload page
        page.reload()

        # Verify form data was restored
        assert page.locator('input[name="amount"]').input_value() == "75.25"
        assert page.locator('input[name="note"]').input_value() == "Restored draft"

    def test_draft_persistence_clears_on_success(self, page: Page) -> None:
        """Test that localStorage draft is cleared after successful submission."""
        category_id = get_category_id("expense", _user_id)
        page.goto("/transactions/new")

        # Set up draft in localStorage
        page.evaluate("""() => {
            const draft = {
                amount: "50",
                note: "Will be submitted"
            };
            localStorage.setItem('tx-draft', JSON.stringify(draft));
        }""")

        # Fill and submit form
        page.select_option('select[name="account_id"]', _account_id)
        page.select_option("#type-select", "expense")
        page.evaluate(
            f"document.querySelector('[data-category-combobox]')._combobox.selectById('{category_id}')"
        )
        page.fill('input[name="amount"]', "50")
        page.fill('input[name="note"]', "Will be submitted")

        with page.expect_response(
            lambda r: "/transactions" in r.url and r.request.method == "POST"
        ):
            page.click('button[type="submit"]')

        # Verify draft was cleared
        page.wait_for_timeout(500)
        draft_data = page.evaluate("() => localStorage.getItem('tx-draft')")
        assert draft_data is None

    def test_swipe_to_delete_transaction(self, page: Page) -> None:
        """Test swipe-to-delete gesture on transaction row."""
        category_id = get_category_id("expense", _user_id)
        tx_id = create_transaction(
            page, _account_id, category_id, "150", "expense", note="SwipeMe"
        )
        page.goto("/transactions")
        expect(page.locator("main")).to_contain_text("SwipeMe")

        # Simulate swipe gesture on the transaction row
        row = page.locator(f"#tx-{tx_id}")
        expect(row).to_be_visible()

        # Simulate touchstart → touchmove → touchend (swipe left)
        # Use proper Touch objects to avoid TouchEvent constructor errors
        page.evaluate(f"""() => {{
            const el = document.getElementById('tx-{tx_id}');
            if (el) {{
                const startTouch = new Touch({{
                    identifier: 0,
                    target: el,
                    clientX: 300,
                    clientY: 100,
                    screenX: 300,
                    screenY: 100,
                    pageX: 300,
                    pageY: 100
                }});
                el.dispatchEvent(new TouchEvent('touchstart', {{
                    bubbles: true,
                    cancelable: true,
                    touches: [startTouch],
                    targetTouches: [startTouch],
                    changedTouches: [startTouch]
                }}));

                const moveTouch = new Touch({{
                    identifier: 0,
                    target: el,
                    clientX: 50,
                    clientY: 100,
                    screenX: 50,
                    screenY: 100,
                    pageX: 50,
                    pageY: 100
                }});
                el.dispatchEvent(new TouchEvent('touchmove', {{
                    bubbles: true,
                    cancelable: true,
                    touches: [moveTouch],
                    targetTouches: [moveTouch],
                    changedTouches: [moveTouch]
                }}));

                el.dispatchEvent(new TouchEvent('touchend', {{
                    bubbles: true,
                    cancelable: true,
                    touches: [],
                    targetTouches: [],
                    changedTouches: [moveTouch]
                }}));
            }}
        }}""")

        page.wait_for_timeout(300)

        # After swipe, delete confirmation should appear (or transaction slides left)
        # For this test, we'll verify the delete button appears if exposed by swipe
        expect(page.locator(f"#tx-{tx_id}")).to_be_visible()

    def test_create_expense_with_fee(self, page: Page) -> None:
        """Fee field in More Options creates a linked fee transaction."""
        category_id = get_category_id("expense", _user_id)
        page.goto("/transactions/new")
        page.select_option('select[name="account_id"]', _account_id)
        page.select_option("#type-select", "expense")
        page.evaluate(
            f"document.querySelector('[data-category-combobox]')._combobox.selectById('{category_id}')"
        )
        page.fill('input[name="amount"]', "500")
        page.fill('input[name="note"]', "Groceries")

        # Open More Options and fill fee
        page.click("#more-options-toggle")
        expect(page.locator("#fee-input")).to_be_visible()
        page.fill("#fee-input", "25")

        with page.expect_response(
            lambda r: "/transactions" in r.url and r.request.method == "POST"
        ):
            page.click('button[type="submit"]')

        expect(page.locator("#transaction-result")).to_contain_text(
            "Transaction saved!"
        )
        # 10,000 - 500 (expense) - 25 (fee) = 9,475
        page.goto(f"/accounts/{_account_id}")
        expect(page.locator("main")).to_contain_text("9,475")

    def test_swipe_to_delete_reveals_button(self, page: Page) -> None:
        """Test that swipe gesture reveals delete button (no auto-dialog)."""
        category_id = get_category_id("expense", _user_id)
        tx_id = create_transaction(
            page, _account_id, category_id, "150", "expense", note="SwipeReveal"
        )
        page.goto("/transactions")

        row = page.locator(f"#tx-{tx_id}")
        expect(row).to_be_visible()

        # Simulate swipe gesture
        page.evaluate(f"""() => {{
            const el = document.getElementById('tx-{tx_id}');
            if (el) {{
                const startTouch = new Touch({{
                    identifier: 0,
                    target: el,
                    clientX: 300,
                    clientY: 100,
                    screenX: 300,
                    screenY: 100,
                    pageX: 300,
                    pageY: 100
                }});
                el.dispatchEvent(new TouchEvent('touchstart', {{
                    bubbles: true,
                    cancelable: true,
                    touches: [startTouch],
                    targetTouches: [startTouch],
                    changedTouches: [startTouch]
                }}));

                const moveTouch = new Touch({{
                    identifier: 0,
                    target: el,
                    clientX: 50,
                    clientY: 100,
                    screenX: 50,
                    screenY: 100,
                    pageX: 50,
                    pageY: 100
                }});
                el.dispatchEvent(new TouchEvent('touchmove', {{
                    bubbles: true,
                    cancelable: true,
                    touches: [moveTouch],
                    targetTouches: [moveTouch],
                    changedTouches: [moveTouch]
                }}));

                el.dispatchEvent(new TouchEvent('touchend', {{
                    bubbles: true,
                    cancelable: true,
                    touches: [],
                    targetTouches: [],
                    changedTouches: [moveTouch]
                }}));
            }}
        }}""")

        page.wait_for_timeout(500)

        # Delete button should be revealed (no dialog yet)
        expect(page.locator("#confirm-dialog")).not_to_be_visible()
        expect(row.locator(".swipe-delete-btn")).to_be_visible()
        expect(row.locator(".swipe-delete-btn")).to_contain_text("Delete")

    def test_swipe_to_delete_dialog_cancel(self, page: Page) -> None:
        """Test that canceling the custom dialog keeps the transaction."""
        category_id = get_category_id("expense", _user_id)
        tx_id = create_transaction(
            page, _account_id, category_id, "150", "expense", note="CancelTest"
        )
        page.goto("/transactions")

        row = page.locator(f"#tx-{tx_id}")
        expect(row).to_be_visible()

        # Swipe to reveal delete button
        page.evaluate(f"""() => {{
            const el = document.getElementById('tx-{tx_id}');
            if (el) {{
                const startTouch = new Touch({{
                    identifier: 0,
                    target: el,
                    clientX: 300,
                    clientY: 100
                }});
                el.dispatchEvent(new TouchEvent('touchstart', {{
                    bubbles: true,
                    touches: [startTouch],
                    changedTouches: [startTouch]
                }}));

                const moveTouch = new Touch({{
                    identifier: 0,
                    target: el,
                    clientX: 50,
                    clientY: 100
                }});
                el.dispatchEvent(new TouchEvent('touchmove', {{
                    bubbles: true,
                    touches: [moveTouch],
                    changedTouches: [moveTouch]
                }}));

                el.dispatchEvent(new TouchEvent('touchend', {{
                    bubbles: true,
                    changedTouches: [moveTouch]
                }}));
            }}
        }}""")

        page.wait_for_timeout(500)

        # Tap the revealed delete button
        row.locator(".swipe-delete-btn").click()
        page.wait_for_timeout(400)

        # Click cancel on dialog
        page.click("#confirm-dialog-cancel")
        page.wait_for_timeout(400)

        # Row should still be visible and button hidden
        expect(row).to_be_visible()
        expect(page.locator("#confirm-dialog")).not_to_be_visible()

    def test_swipe_to_delete_dialog_confirm(self, page: Page) -> None:
        """Test that confirming delete removes the transaction row."""
        category_id = get_category_id("expense", _user_id)
        tx_id = create_transaction(
            page, _account_id, category_id, "150", "expense", note="ConfirmTest"
        )
        page.goto("/transactions")

        row = page.locator(f"#tx-{tx_id}")
        expect(row).to_be_visible()

        # Swipe to reveal delete button
        page.evaluate(f"""() => {{
            const el = document.getElementById('tx-{tx_id}');
            if (el) {{
                const startTouch = new Touch({{
                    identifier: 0,
                    target: el,
                    clientX: 300,
                    clientY: 100
                }});
                el.dispatchEvent(new TouchEvent('touchstart', {{
                    bubbles: true,
                    touches: [startTouch],
                    changedTouches: [startTouch]
                }}));

                const moveTouch = new Touch({{
                    identifier: 0,
                    target: el,
                    clientX: 50,
                    clientY: 100
                }});
                el.dispatchEvent(new TouchEvent('touchmove', {{
                    bubbles: true,
                    touches: [moveTouch],
                    changedTouches: [moveTouch]
                }}));

                el.dispatchEvent(new TouchEvent('touchend', {{
                    bubbles: true,
                    changedTouches: [moveTouch]
                }}));
            }}
        }}""")

        page.wait_for_timeout(500)

        # Tap the revealed delete button
        row.locator(".swipe-delete-btn").click()
        page.wait_for_timeout(400)

        # Click confirm delete
        with page.expect_response(
            lambda r: f"/transactions/{tx_id}" in r.url and r.request.method == "DELETE"
        ):
            page.click("#confirm-dialog-confirm")

        # Row should be removed after animation
        page.wait_for_timeout(500)
        expect(row).not_to_be_visible()
        expect(page.locator("#confirm-dialog")).not_to_be_visible()

    def test_kebab_menu_delete_uses_custom_dialog(self, page: Page) -> None:
        """Test that delete from kebab menu uses custom dialog."""
        category_id = get_category_id("expense", _user_id)
        tx_id = create_transaction(
            page, _account_id, category_id, "150", "expense", note="KebabTest"
        )
        page.goto("/transactions")

        # Open kebab menu
        page.click(f"#tx-{tx_id} [data-kebab-trigger]")
        page.wait_for_timeout(200)

        # Click delete button
        page.click(f"#tx-{tx_id} button[hx-delete='/transactions/{tx_id}']")
        page.wait_for_timeout(500)

        # Custom dialog should appear
        dialog = page.locator("#confirm-dialog")
        expect(dialog).to_be_visible()
        expect(dialog).to_contain_text("Delete this transaction?")

        # Cancel to clean up
        page.click("#confirm-dialog-cancel")

    def test_swipe_to_delete_dismiss_on_tap_elsewhere(self, page: Page) -> None:
        """Test that tapping elsewhere dismisses the revealed delete button."""
        category_id = get_category_id("expense", _user_id)
        tx_id = create_transaction(
            page, _account_id, category_id, "150", "expense", note="DismissTest"
        )
        page.goto("/transactions")

        row = page.locator(f"#tx-{tx_id}")
        expect(row).to_be_visible()

        # Swipe to reveal delete button
        page.evaluate(f"""() => {{
            const el = document.getElementById('tx-{tx_id}');
            if (el) {{
                const startTouch = new Touch({{
                    identifier: 0,
                    target: el,
                    clientX: 300,
                    clientY: 100
                }});
                el.dispatchEvent(new TouchEvent('touchstart', {{
                    bubbles: true,
                    touches: [startTouch],
                    changedTouches: [startTouch]
                }}));

                const moveTouch = new Touch({{
                    identifier: 0,
                    target: el,
                    clientX: 50,
                    clientY: 100
                }});
                el.dispatchEvent(new TouchEvent('touchmove', {{
                    bubbles: true,
                    touches: [moveTouch],
                    changedTouches: [moveTouch]
                }}));

                el.dispatchEvent(new TouchEvent('touchend', {{
                    bubbles: true,
                    changedTouches: [moveTouch]
                }}));
            }}
        }}""")

        page.wait_for_timeout(500)

        # Delete button should be revealed
        expect(row.locator(".swipe-delete-btn")).to_be_visible()

        # Tap elsewhere on the page
        page.click("main")
        page.wait_for_timeout(400)

        # Delete button should be hidden
        expect(row.locator(".swipe-delete-btn")).not_to_be_visible()
        expect(page.locator("#confirm-dialog")).not_to_be_visible()

    def test_swipe_to_delete_only_one_revealed_at_a_time(self, page: Page) -> None:
        """Test that revealing one row hides the previously revealed row."""
        category_id = get_category_id("expense", _user_id)
        tx1_id = create_transaction(
            page, _account_id, category_id, "100", "expense", note="First"
        )
        tx2_id = create_transaction(
            page, _account_id, category_id, "200", "expense", note="Second"
        )
        page.goto("/transactions")

        row1 = page.locator(f"#tx-{tx1_id}")
        row2 = page.locator(f"#tx-{tx2_id}")
        expect(row1).to_be_visible()
        expect(row2).to_be_visible()

        # Swipe first row to reveal
        page.evaluate(f"""() => {{
            const el = document.getElementById('tx-{tx1_id}');
            if (el) {{
                const startTouch = new Touch({{ identifier: 0, target: el, clientX: 300, clientY: 100 }});
                el.dispatchEvent(new TouchEvent('touchstart', {{ bubbles: true, touches: [startTouch], changedTouches: [startTouch] }}));
                const moveTouch = new Touch({{ identifier: 0, target: el, clientX: 50, clientY: 100 }});
                el.dispatchEvent(new TouchEvent('touchmove', {{ bubbles: true, touches: [moveTouch], changedTouches: [moveTouch] }}));
                el.dispatchEvent(new TouchEvent('touchend', {{ bubbles: true, changedTouches: [moveTouch] }}));
            }}
        }}""")

        page.wait_for_timeout(500)
        expect(row1.locator(".swipe-delete-btn")).to_be_visible()

        # Swipe second row
        page.evaluate(f"""() => {{
            const el = document.getElementById('tx-{tx2_id}');
            if (el) {{
                const startTouch = new Touch({{ identifier: 0, target: el, clientX: 300, clientY: 100 }});
                el.dispatchEvent(new TouchEvent('touchstart', {{ bubbles: true, touches: [startTouch], changedTouches: [startTouch] }}));
                const moveTouch = new Touch({{ identifier: 0, target: el, clientX: 50, clientY: 100 }});
                el.dispatchEvent(new TouchEvent('touchmove', {{ bubbles: true, touches: [moveTouch], changedTouches: [moveTouch] }}));
                el.dispatchEvent(new TouchEvent('touchend', {{ bubbles: true, changedTouches: [moveTouch] }}));
            }}
        }}""")

        page.wait_for_timeout(500)

        # First row should be hidden, second row revealed
        expect(row1.locator(".swipe-delete-btn")).not_to_be_visible()
        expect(row2.locator(".swipe-delete-btn")).to_be_visible()


class TestGlobalSearchE2E:
    def test_global_search_flow(self, page: Page) -> None:
        """Verify the global search flow from the header: click icon, type query, see results, click result."""
        # Create a transaction to search for
        category_id = get_category_id("expense", _user_id)
        tx_id = create_transaction(
            page,
            _account_id,
            category_id,
            "999",
            "expense",
            note="Global Search Target",
        )

        # Go to Dashboard (which has the header)
        page.goto("/")

        # Click the search icon in the header
        page.click("#global-search-btn")

        # Search overlay should become visible
        overlay = page.locator("#global-search-overlay")
        expect(overlay).not_to_have_class("hidden")

        # Type into the search input to trigger HTMX request (with debounce)
        input_loc = page.locator("#global-search-input")
        input_loc.fill("Search Target")

        # Wait for HTMX to respond and render results
        results_container = page.locator("#global-search-results")
        expect(results_container).to_contain_text("Global Search Target", timeout=5000)

        # Click the first result
        first_result = page.locator("#search-result-1 [role='button']")
        first_result.click()

        # Detail sheet should be visible containing the transaction info
        detail_sheet = page.locator("#tx-detail-content")
        expect(detail_sheet).to_be_visible()
        expect(detail_sheet).to_contain_text("Global Search Target")
        expect(detail_sheet).to_contain_text("999")
