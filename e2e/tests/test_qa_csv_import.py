"""CSV Import tests.

Covers the full CSV import wizard: upload, mapping, preview, submit.
"""
import sys
import os
import io
import csv

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from playwright.sync_api import Page, expect
from conftest import (
    _conn,
    ensure_auth,
    reset_database,
)

_user_id: str = ""
_account_id: str = ""


@pytest.fixture(scope="function", autouse=True)
def db() -> None:
    global _user_id, _account_id
    _user_id = reset_database()
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO institutions (user_id, name, type, display_order) VALUES (%s, 'Test Bank', 'bank', 0) RETURNING id",
                (_user_id,),
            )
            inst_id = str(cur.fetchone()[0])
            cur.execute(
                "INSERT INTO accounts (user_id, institution_id, name, type, currency, current_balance, initial_balance, display_order) VALUES (%s, %s, 'Current', 'current', 'EGP', 10000, 10000, 0) RETURNING id",
                (_user_id, inst_id),
            )
            _account_id = str(cur.fetchone()[0])
        conn.commit()


@pytest.fixture(autouse=True)
def auth(db: None, page: Page) -> None:
    ensure_auth(page)


class TestCSVImport:
    def test_csv_import_wizard_flow(self, page: Page) -> None:
        """Upload a valid CSV, map columns, preview, and submit."""
        page.goto("/settings/import")
        
        # 1. Upload
        csv_content = "Date,Amount,Note\n2026-04-10,-50,Groceries\n2026-04-11,2000,Salary\n"
        page.locator("input[type='file']").set_input_files(
            files=[{"name": "test.csv", "mimeType": "text/csv", "buffer": csv_content.encode("utf-8")}]
        )
        page.locator("main button[type='submit']").click()

        # 2. Mapping
        expect(page).to_have_url(str(page.url))
        expect(page.locator("body")).to_contain_text("Map CSV Columns")
        page.select_option("select[name='col_date']", "Date")
        page.select_option("select[name='col_amount']", "Amount")
        page.select_option("select[name='col_note']", "Note")
        page.select_option("select[name='account_id']", _account_id)
        page.locator("main button[type='submit']").click()
        
        # 3. Preview
        expect(page.locator("body")).to_contain_text("Preview Import")
        expect(page.locator("body")).to_contain_text("Groceries")
        expect(page.locator("body")).to_contain_text("Salary")
        page.locator("button:has-text('Confirm Import')").click()
        
        # 4. Summary
        expect(page.locator("body")).to_contain_text("Import Complete")
        expect(page.locator("body")).to_contain_text("Successfully Created")
        expect(page.locator("body")).to_contain_text("2")
        
        # Verify Balance changed!
        # -50 (expense) + 2000 = 1950. Account was 10000 -> 11950
        page.goto(f"/accounts/{_account_id}")
        expect(page.locator("main")).to_contain_text("11,950")
