import sys
import os
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from playwright.sync_api import Page, expect
from conftest import (
    reset_database,
    ensure_auth,
    seed_basic_data,
    create_transaction,
    _conn
)

_user_id: str = ""

@pytest.fixture(scope="function", autouse=True)
def db() -> None:
    """Reset DB and create test data for fees."""
    global _user_id
    _user_id = reset_database()

@pytest.fixture(autouse=True)
def auth(db: None, page: Page) -> None:
    ensure_auth(page)

class TestFeeAnalyticsE2E:
    def test_fee_analytics_visible_on_reports(self, page: Page) -> None:
        # 1. Seed basic data (bank + account)
        _, account_id = seed_basic_data(page)
        
        # 2. Get the Fees & Charges category ID
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM categories WHERE name->>'en' = 'Fees & Charges' AND user_id = %s",
                    (_user_id,)
                )
                row = cur.fetchone()
                assert row is not None
                cat_id = str(row[0])
        
        # 3. Create a fee transaction via API
        today_iso = datetime.date.today().isoformat()
        create_transaction(
            page,
            account_id=account_id,
            category_id=cat_id,
            amount="25.00",
            tx_type="expense",
            note="Monthly bank fee",
            date=today_iso
        )
        
        # 4. Navigate to reports
        page.goto("/reports")
        
        # 5. Verify Fee Analytics section
        expect(page.locator("h3:has-text('Fee Analytics')")).to_be_visible()
        
        # 6. Verify headline stat
        expect(page.locator("p:has-text('Fees Paid This Year')")).to_be_visible()
        # Amount formatting should be visible (e.g. 25.00)
        expect(page.locator("span:has-text('25.00')").first).to_be_visible()
        
        # 7. Verify breakdown by type (Note parsing should map "Monthly bank fee" to "Other" or we can use "Transfer fee")
        # Let's create another one that specifically maps to Transfer
        create_transaction(
            page,
            account_id=account_id,
            category_id=cat_id,
            amount="10.00",
            tx_type="expense",
            note="Transfer fee",
            date=today_iso
        )
        
        page.reload()
        expect(page.locator("span:has-text('Transfer')")).to_be_visible()
        expect(page.locator("span:has-text('35.00')").first).to_be_visible()
