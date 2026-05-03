"""Dashboard sparkline E2E tests."""

import sys
import os
import json
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from playwright.sync_api import Page, expect
from conftest import (
    _conn,
    ensure_auth,
    reset_database,
)

_user_id: str = ""

@pytest.fixture(scope="function", autouse=True)
def db() -> None:
    global _user_id
    _user_id = reset_database()
    with _conn() as conn:
        with conn.cursor() as cur:
            # Seed an institution and accounts so net worth section shows and has values
            cur.execute("INSERT INTO institutions (user_id, name, type, display_order) VALUES (%s, %s, %s, 0) RETURNING id", (_user_id, 'Test Bank', 'bank'))
            inst_id = cur.fetchone()[0]
            cur.execute("INSERT INTO accounts (user_id, institution_id, name, type, currency, current_balance, initial_balance, display_order) VALUES (%s, %s, %s, %s, %s, %s, %s, 0)", (_user_id, inst_id, 'Current EGP', 'current', 'EGP', 10000, 10000))
            cur.execute("INSERT INTO accounts (user_id, institution_id, name, type, currency, current_balance, initial_balance, display_order) VALUES (%s, %s, %s, %s, %s, %s, %s, 1)", (_user_id, inst_id, 'Current EUR', 'current', 'EUR', 1000, 1000))
            
            # Enable EUR
            cur.execute("INSERT INTO currencies (code, name, symbol, is_enabled, display_order) VALUES ('EUR', '{\"en\": \"Euro\"}', '€', true, 1) ON CONFLICT (code) DO NOTHING")
            cur.execute(
                "UPDATE user_currency_preferences SET active_currency_codes = '[\"EGP\", \"EUR\"]' WHERE user_id = %s",
                (_user_id,)
            )
        conn.commit()

@pytest.fixture(autouse=True)
def auth(db: None, page: Page) -> None:
    ensure_auth(page)

def _seed_history(user_id: str, currency: str, net_worth_values: list[float]):
    """Seed historical snapshots for a user/currency."""
    today = date.today()
    with _conn() as conn:
        with conn.cursor() as cur:
            # Get account ID for this currency
            cur.execute("SELECT id FROM accounts WHERE user_id = %s AND currency = %s LIMIT 1", (user_id, currency))
            acc_row = cur.fetchone()
            acc_id = acc_row[0] if acc_row else None

            for i, val in enumerate(net_worth_values):
                snap_date = today - timedelta(days=len(net_worth_values) - 1 - i)
                cur.execute(
                    "INSERT INTO historical_snapshots (user_id, date, currency, net_worth, daily_spending, daily_income) "
                    "VALUES (%s, %s, %s, %s, 0, 0) "
                    "ON CONFLICT (user_id, date, currency) DO UPDATE SET net_worth = EXCLUDED.net_worth",
                    (user_id, snap_date, currency, val)
                )
                if acc_id:
                    cur.execute(
                        "INSERT INTO account_snapshots (id, user_id, account_id, date, balance) "
                        "VALUES (gen_random_uuid(), %s, %s, %s, %s)",
                        (user_id, acc_id, snap_date, val)
                    )
        conn.commit()

def test_egp_sparkline_visible_with_history(page: Page):
    """Verify EGP sparkline shows when history exists."""
    _seed_history(_user_id, "EGP", [1000.0, 1100.0, 1200.0, 1100.0, 1500.0])
    page.goto("/")
    expect(page.locator("#section-net-worth svg.chart-sparkline")).to_be_visible()

def test_eur_sparkline_visible_when_selected(page: Page):
    """Verify EUR sparkline shows when EUR selected and has history."""
    _seed_history(_user_id, "EUR", [50.0, 55.0, 60.0, 55.0, 70.0])
    
    # Pre-select EUR for the user
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE user_currency_preferences SET selected_display_currency = 'EUR' WHERE user_id = %s", (_user_id,))
        conn.commit()

    page.goto("/")
    expect(page.locator("#section-net-worth svg.chart-sparkline")).to_be_visible()
    # Net worth comes from account balance (1000.00), not history (70.00)
    expect(page.locator("#section-net-worth")).to_contain_text("1,000.00")
    # Trend comes from history: (70 - 50) / 50 = 40%
    expect(page.locator("#section-net-worth")).to_contain_text("40.0%")

def test_no_sparkline_when_no_history(page: Page):
    """Verify no sparkline when no snapshots exist."""
    page.goto("/")
    expect(page.locator("#section-net-worth svg.chart-sparkline")).not_to_be_visible()
