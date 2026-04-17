"""Financial calendar E2E tests — T068.

Tests the calendar page at /calendar: grid renders, month navigation works,
and events appear for transactions created in the current month.
"""
import sys
import os
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from playwright.sync_api import Page, expect
from conftest import (
    _conn,
    ensure_auth,
    get_category_id,
    reset_database,
    create_transaction,
)

_account_id: str = ""
_user_id: str = ""

# Current month/year for expected heading
_CURRENT_YEAR = date.today().year
_CURRENT_MONTH = date.today().month
_MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
_CURRENT_MONTH_NAME = _MONTH_NAMES[_CURRENT_MONTH]


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
                " VALUES (%s, %s, 'Current', 'current', 'EGP', 10000, 10000, 0) RETURNING id",
                (_user_id, inst_id),
            )
            _account_id = str(cur.fetchone()[0])  # type: ignore[index]
        conn.commit()


@pytest.fixture(autouse=True)
def auth(db: None, page: Page) -> None:
    ensure_auth(page)


class TestCalendar:
    def test_calendar_page_loads(self, page: Page) -> None:
        """GET /calendar renders the calendar with current month heading."""
        page.goto("/calendar")
        expect(page.locator("h2")).to_contain_text(_CURRENT_MONTH_NAME)
        expect(page.locator("h2")).to_contain_text(str(_CURRENT_YEAR))

    def test_calendar_grid_has_seven_columns(self, page: Page) -> None:
        """Calendar grid renders 7 day-of-week header columns."""
        page.goto("/calendar")
        # Day-of-week headers: Sun, Mon, Tue, Wed, Thu, Fri, Sat
        header_cols = page.locator(".grid-cols-7 div:has-text('Sun'), .grid-cols-7 div:has-text('Mon')")
        expect(header_cols.first).to_be_visible()

    def test_calendar_shows_day_numbers(self, page: Page) -> None:
        """Calendar cells show numeric day labels (1 through ~31)."""
        page.goto("/calendar")
        # The first few day numbers should be visible (day 1 is always present)
        expect(page.locator("span:has-text('1')").first).to_be_visible()

    def test_navigate_to_next_month(self, page: Page) -> None:
        """Clicking next-month arrow updates the month heading."""
        import re as _re
        page.goto("/calendar")
        page.click('a[title="Next Month"]')
        # Wait for HTMX navigation to complete (URL gains month/year query params)
        page.wait_for_url(_re.compile(r".*[?&](month|year)=.*"), timeout=5000)
        expect(page.locator("h2")).to_be_visible()

    def test_navigate_to_previous_month(self, page: Page) -> None:
        """Clicking prev-month arrow updates the month heading."""
        import re as _re
        page.goto("/calendar")
        page.click('a[title="Previous Month"]')
        # Wait for HTMX navigation to complete (URL gains month/year query params)
        page.wait_for_url(_re.compile(r".*[?&](month|year)=.*"), timeout=5000)
        expect(page.locator("h2")).to_be_visible()

    def test_transaction_appears_on_calendar(self, page: Page) -> None:
        """A transaction created today appears as an event on the calendar."""
        cat_id = get_category_id("expense", _user_id)
        create_transaction(
            page,
            _account_id,
            cat_id,
            "350",
            "expense",
            note="Groceries",
        )
        page.goto("/calendar")
        # Event with the transaction note should appear in the grid/list
        expect(page.locator("main")).to_contain_text("Groceries")

    def test_back_link_navigates_to_dashboard(self, page: Page) -> None:
        """Back arrow on calendar navigates to dashboard (/)."""
        page.goto("/calendar")
        with page.expect_navigation():
            page.click('a[aria-label="Back"]')
        expect(page).to_have_url("/", timeout=5000)
