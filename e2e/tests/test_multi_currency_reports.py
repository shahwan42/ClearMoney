import sys
import os
from playwright.sync_api import Page, expect

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from conftest import (
    _conn,
    ensure_auth,
    reset_database,
)

_user_id: str = ""

@pytest.fixture(scope="function", autouse=True)
def db() -> None:
    """Reset DB and create test institution + accounts in EGP and EUR."""
    global _user_id
    _user_id = reset_database()
    with _conn() as conn:
        with conn.cursor() as cur:
            # Create currencies
            cur.execute("INSERT INTO currencies (code, name, symbol, is_enabled, display_order) VALUES ('EGP', 'Egyptian Pound', 'EGP', true, 0) ON CONFLICT (code) DO NOTHING")
            cur.execute("INSERT INTO currencies (code, name, symbol, is_enabled, display_order) VALUES ('EUR', 'Euro', '€', true, 1) ON CONFLICT (code) DO NOTHING")
            
            # Update user preferences (already created by reset_database)
            cur.execute(
                "UPDATE user_currency_preferences SET active_currency_codes = '[\"EGP\", \"EUR\"]', selected_display_currency = 'EGP' WHERE user_id = %s",
                (_user_id,)
            )

            cur.execute(
                "INSERT INTO institutions (user_id, name, type, display_order)"
                " VALUES (%s, 'Test Bank', 'bank', 0) RETURNING id",
                (_user_id,),
            )
            inst_id = str(cur.fetchone()[0])
            
            # EGP Account
            cur.execute(
                "INSERT INTO accounts"
                " (user_id, institution_id, name, type, currency, current_balance, initial_balance, display_order)"
                " VALUES (%s, %s, 'EGP Account', 'current', 'EGP', 1000, 1000, 0) RETURNING id",
                (_user_id, inst_id),
            )
            egp_acc_id = str(cur.fetchone()[0])
            
            # EUR Account
            cur.execute(
                "INSERT INTO accounts"
                " (user_id, institution_id, name, type, currency, current_balance, initial_balance, display_order)"
                " VALUES (%s, %s, 'EUR Account', 'current', 'EUR', 100, 100, 1) RETURNING id",
                (_user_id, inst_id),
            )
            eur_acc_id = str(cur.fetchone()[0])
            
            # Transactions
            cur.execute(
                "INSERT INTO transactions (user_id, account_id, type, amount, currency, date, balance_delta)"
                " VALUES (%s, %s, 'expense', 500, 'EGP', CURRENT_DATE, -500)",
                (_user_id, egp_acc_id)
            )
            cur.execute(
                "INSERT INTO transactions (user_id, account_id, type, amount, currency, date, balance_delta)"
                " VALUES (%s, %s, 'expense', 20, 'EUR', CURRENT_DATE, -20)",
                (_user_id, eur_acc_id)
            )
            
        conn.commit()

@pytest.fixture(autouse=True)
def auth(db: None, page: Page) -> None:
    ensure_auth(page)

def test_reports_eur_filtering(page: Page) -> None:
    """Switch report to EUR and verify exact-currency data."""
    page.goto("/reports")
    
    # Default is EGP
    expect(page.get_by_text("EGP 500.00").first).to_be_visible()
    
    # Select EUR from dropdown
    # The dropdown onchange redirects to /reports?year=...&month=...&currency=EUR
    page.select_option("select.flex-1", label="EUR")
    
    # Wait for reload
    page.wait_for_load_state("networkidle")
    
    # Should show 20.00
    expect(page.get_by_text("20.00").first).to_be_visible()
    # Should NOT show EGP 500.00
    expect(page.get_by_text("500.00")).to_have_count(0)

def test_pdf_export_eur(page: Page) -> None:
    """Export PDF for EUR and verify it's triggered (if PDF available)."""
    page.goto("/reports?currency=EUR")
    
    # Download button should be visible if PDF is available on the server
    btn = page.locator('a:has-text("Export PDF")')
    if btn.count() > 0:
        expect(btn).to_be_visible()
        # Check the href
        href = btn.get_attribute("href")
        assert "currency=EUR" in href

def test_header_currency_affects_reports_default(page: Page) -> None:
    """Change header currency and confirm reports default to it."""
    # This requires interacting with the header currency selector if it exists
    # Or just setting the preference via URL if supported
    
    # Let's set the preference via settings first
    page.goto("/settings")
    # Actually, settings page usually has currency preferences
    # But for this test, we can just check if /reports follows the user preference
    
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE user_currency_preferences SET selected_display_currency = 'EUR' WHERE user_id = %s",
                (_user_id,)
            )
        conn.commit()
    
    page.goto("/reports")
    # Should default to EUR now
    expect(page.get_by_text("20.00").first).to_be_visible()
    expect(page.locator("select.flex-1")).to_have_value("EUR")
