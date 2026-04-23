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
        create_transaction(
            page, account_id, category_id, "250", "expense", note="Lunch"
        )

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

    def test_reordering_recent_transactions_above_spending(self, page: Page) -> None:
        """Verify Recent Transactions appears before Spending sections."""
        _, account_id = seed_basic_data(page)
        category_id = get_category_id("expense", _user_id)
        create_transaction(page, account_id, category_id, "100", "expense")

        page.goto("/")

        # Get all section titles in order
        titles = page.locator("h2").all_text_contents()
        clean_titles = [t.strip() for t in titles if t.strip()]

        # Recent Transactions should be before This Month vs Last (Spending)
        idx_recent = clean_titles.index("Recent Transactions")
        idx_spending = clean_titles.index("This Month vs Last")
        assert idx_recent < idx_spending

    def test_collapse_expand_persistence(self, page: Page) -> None:
        """Verify collapsing a section hides content, shows summary, and persists after reload."""
        seed_basic_data(page)
        page.goto("/")

        # Locate Net Worth section
        section = page.locator("#section-net-worth")
        header = section.locator("[data-dashboard-toggle]")
        content = page.locator("#content-net-worth")
        summary = page.locator("#summary-net-worth")

        # Initially expanded
        expect(content).to_be_visible()
        expect(summary).not_to_be_visible()

        # Click header to collapse
        header.click()

        # Verify collapsed state
        expect(content).not_to_be_visible()
        expect(summary).to_be_visible()
        expect(summary).to_contain_text("EGP")

        # Reload page
        page.reload()

        # Verify persistence (should stay collapsed)
        section = page.locator("#section-net-worth")
        content = page.locator("#content-net-worth")
        summary = page.locator("#summary-net-worth")

        expect(content).not_to_be_visible()
        expect(summary).to_be_visible()

        # Click again to expand
        header = section.locator("[data-dashboard-toggle]")
        header.click()

        # Verify expanded state
        expect(content).to_be_visible()
        expect(summary).not_to_be_visible()

    def test_keyboard_accessibility(self, page: Page) -> None:
        """Verify section toggle works with keyboard (Enter/Space)."""
        seed_basic_data(page)
        page.goto("/")

        section = page.locator("#section-net-worth")
        header = section.locator("[data-dashboard-toggle]")
        content = page.locator("#content-net-worth")

        # Initial state: expanded
        expect(content).to_be_visible()

        # Focus and press Enter
        header.focus()
        page.keyboard.press("Enter")
        expect(content).not_to_be_visible()

        # Press Space
        page.keyboard.press("Space")
        expect(content).to_be_visible()


def _create_budget_via_sql(
    user_id: str, category_id: str, monthly_limit: int = 3000
) -> str:
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
        """Dashboard shows spending pace section when a last-month baseline exists."""
        _, account_id = seed_basic_data(page)
        category_id = get_category_id("expense", _user_id)
        from datetime import date, timedelta

        last_month = date.today().replace(day=1) - timedelta(days=1)
        last_month_first = last_month.replace(day=1)
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO transactions"
                    " (user_id, account_id, type, amount, currency, date, balance_delta)"
                    " VALUES (%s, %s, 'expense', 1200, 'EGP', %s, -1200)",
                    (_user_id, account_id, last_month_first),
                )
            conn.commit()

        create_transaction(page, account_id, category_id, "500", "expense")

        page.goto("/")
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


class TestCashFlowForecast:
    def test_forecast_card_visible_with_recurring_rules(self, page: Page) -> None:
        """Cash flow forecast card shows when recurring rules exist."""
        global _user_id
        _, account_id = seed_basic_data(page)

        # Create a recurring income rule via SQL
        category_id = get_category_id("income", _user_id)
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO recurring_rules "
                    "(user_id, template_transaction, frequency, next_due_date, is_active, auto_confirm) "
                    "VALUES (%s, %s, 'monthly', '2026-04-25', true, false) RETURNING id",
                    (
                        _user_id,
                        f'{{"type": "income", "amount": 5000, "currency": "EGP", "account_id": "{account_id}", "note": "Salary"}}',
                    ),
                )
            conn.commit()

        page.goto("/")

        # Forecast card should be visible
        expect(page.locator("main")).to_contain_text("Cash Flow Forecast")
        expect(page.locator("main")).to_contain_text("Projected")
        expect(page.locator("main")).to_contain_text("Expected Income")

    def test_forecast_shows_negative_warning(self, page: Page) -> None:
        """Forecast displays warning when balance goes negative."""
        global _user_id
        _, account_id = seed_basic_data(page)

        # Create a large recurring expense that exceeds balance
        category_id = get_category_id("expense", _user_id)
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO recurring_rules "
                    "(user_id, template_transaction, frequency, next_due_date, is_active, auto_confirm) "
                    "VALUES (%s, %s, 'monthly', '2026-04-25', true, false) RETURNING id",
                    (
                        _user_id,
                        f'{{"type": "expense", "amount": 20000, "currency": "EGP", "account_id": "{account_id}", "note": "Big Purchase"}}',
                    ),
                )
            conn.commit()

        page.goto("/")

        # Warning should be visible
        expect(page.locator("main")).to_contain_text("Warning")
        expect(page.locator("main")).to_contain_text("negative")
