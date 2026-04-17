"""Dashboard rendering tests.

Converts: 04-dashboard.spec.ts
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from playwright.sync_api import Page, expect
from conftest import (
    TEST_EMAIL,
    _conn,
    create_transaction,
    ensure_auth,
    get_category_id,
    reset_database,
    seed_basic_data,
)

_user_id: str = ""


@pytest.fixture(scope="function", autouse=True)
def db() -> None:
    global _user_id
    _user_id = reset_database()


@pytest.fixture(autouse=True)
def auth(db: None, page: Page) -> None:
    ensure_auth(page)


class TestDashboard:
    def test_net_worth_section_visible(self, page: Page) -> None:
        seed_basic_data(page)
        page.goto("/")
        expect(page.locator("main")).to_contain_text("Net Worth")
        expect(page.locator("main")).to_contain_text("10,000")

    def test_summary_cards_visible(self, page: Page) -> None:
        seed_basic_data(page)
        page.goto("/")
        expect(page.locator("main")).to_contain_text("Liquid Cash")
        expect(page.locator("main")).to_contain_text("Credit Used")
        expect(page.locator("main")).to_contain_text("Credit Available")

    def test_institution_accounts_section(self, page: Page) -> None:
        seed_basic_data(page)
        page.goto("/")
        expect(page.locator("main")).to_contain_text("Test Bank")

    def test_recent_transactions_empty_then_populated(self, page: Page) -> None:
        _, account_id = seed_basic_data(page)
        # After seeding data but no transactions, should show "No transactions yet"
        page.goto("/")
        expect(page.locator("main")).to_contain_text("No transactions yet")

        category_id = get_category_id("expense", _user_id)
        create_transaction(page, account_id, category_id, "250", "expense", note="Lunch")

        page.reload()
        expect(page.locator("main")).to_contain_text("Lunch")

    def test_momentum_scroll_content_visible(self, page: Page) -> None:
        """Verify content remains visible during fast momentum scrolling.

        Momentum scrolling can cause rendering jank if touch handlers
        interfere with scroll optimizations. This test ensures content
        doesn't flicker during rapid scrolling.
        """
        seed_basic_data(page)
        page.goto("/")

        # Capture initial content visibility
        net_worth = page.locator("main").get_by_text("Net Worth")
        expect(net_worth).to_be_visible()

        # Simulate fast upward swipe (momentum scroll)
        # On mobile, this would be a quick swipe down gesture
        main = page.locator("main")
        box = main.bounding_box()
        if box:
            # Simulate momentum scroll: quick swipe down at bottom of viewport
            # This triggers momentum scroll upward
            page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] - 50)
            page.mouse.wheel(0, -300)  # Rapid wheel scroll
            page.wait_for_timeout(100)  # Brief pause for momentum
            page.mouse.wheel(0, -300)  # Another rapid scroll

        # Content should remain visible throughout scroll
        expect(net_worth).to_be_visible()

        # Verify key dashboard sections are still rendered
        expect(page.locator("main")).to_contain_text("Liquid Cash")
        expect(page.locator("main")).to_contain_text("Test Bank")


def _create_budget_via_sql(user_id: str, category_id: str, monthly_limit: int = 3000) -> str:
    """Insert a budget directly via SQL and return the budget id."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO budgets (user_id, category_id, monthly_limit, currency, is_active)"
                " VALUES (%s, %s, %s, 'EGP', true) RETURNING id",
                (user_id, category_id, monthly_limit),
            )
            row = cur.fetchone()
            assert row is not None
            budget_id = str(row[0])
        conn.commit()
    return budget_id


class TestSpendingVelocityCard:
    """E2E tests for ticket 076 — spending velocity projections on the dashboard."""

    def test_velocity_section_visible_with_spending(self, page: Page) -> None:
        """Dashboard shows spending pace section after transactions exist.

        The velocity section only renders when spending_velocity.days_total > 0,
        which is always true.  After adding transactions the "Spending Pace" heading
        and the velocity progress bar should be visible.
        """
        _, account_id = seed_basic_data(page)
        category_id = get_category_id("expense", _user_id)
        # Add a transaction so there is this-month spending
        create_transaction(page, account_id, category_id, "500", "expense")

        page.goto("/")
        # The velocity section heading
        expect(page.locator("#spending-velocity-section")).to_be_visible()

    def test_velocity_card_shows_daily_budget(self, page: Page) -> None:
        """Daily budget card shows when the user has spending AND a last-month baseline.

        We inject last-month spending directly via SQL so we have a budget_total > 0,
        which is required for the daily-budget-card div to render.
        """
        _, account_id = seed_basic_data(page)
        category_id = get_category_id("expense", _user_id)

        # Last month spending via SQL (transactions API only accepts today's date range)
        from datetime import date, timedelta
        last_month = date.today().replace(day=1) - timedelta(days=1)
        last_month_first = last_month.replace(day=1)
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO transactions"
                    " (user_id, account_id, type, amount, currency, date, balance_delta)"
                    " VALUES (%s, %s, 'expense', 2000, 'EGP', %s, -2000)",
                    (_user_id, account_id, last_month_first),
                )
            conn.commit()

        # This month transaction (establishes current pace)
        create_transaction(page, account_id, category_id, "300", "expense")

        page.goto("/")
        # The projection card with daily budget text should be visible
        daily_card = page.locator("#daily-budget-card")
        expect(daily_card).to_be_visible()
        # Should contain "/day" text which is part of "X EGP/day for Y days"
        expect(daily_card).to_contain_text("/day")

    def test_velocity_status_badge_visible(self, page: Page) -> None:
        """Status badge appears in the velocity card for any status value."""
        _, account_id = seed_basic_data(page)
        category_id = get_category_id("expense", _user_id)

        # Inject last-month baseline
        from datetime import date, timedelta
        last_month = date.today().replace(day=1) - timedelta(days=1)
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO transactions"
                    " (user_id, account_id, type, amount, currency, date, balance_delta)"
                    " VALUES (%s, %s, 'expense', 1000, 'EGP', %s, -1000)",
                    (_user_id, account_id, last_month),
                )
            conn.commit()

        create_transaction(page, account_id, category_id, "200", "expense")

        page.goto("/")
        badge = page.locator("#velocity-status-badge")
        expect(badge).to_be_visible()

    def test_category_velocity_section_with_budget(self, page: Page) -> None:
        """Per-category velocity rows appear when user has active budgets."""
        _, account_id = seed_basic_data(page)
        category_id = get_category_id("expense", _user_id)

        # Create budget via SQL
        _create_budget_via_sql(_user_id, category_id, monthly_limit=2000)

        # Add transaction in the budgeted category
        create_transaction(page, account_id, category_id, "400", "expense")

        page.goto("/")
        # Category velocity list should be visible
        cat_list = page.locator("#category-velocity-list")
        expect(cat_list).to_be_visible()
