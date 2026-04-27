import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from playwright.sync_api import Page, expect
from conftest import reset_database, ensure_auth

@pytest.fixture(autouse=True)
def setup_data():
    reset_database()

def test_budgets_hint(page: Page):
    ensure_auth(page)
    page.goto("http://localhost:8765/budgets")
    
    # Verify hint is visible
    hint = page.locator("#budgets-hint")
    expect(hint).to_be_visible()
    expect(hint).to_contain_text("Set spending limits per category")
    
    # Dismiss hint via "Got it"
    page.get_by_role("button", name="Got it").click()
    expect(hint).to_be_hidden()
    
    # Reload and verify it stays hidden
    page.reload()
    expect(page.locator("#budgets-hint")).to_be_hidden()

def test_people_hint(page: Page):
    ensure_auth(page)
    page.goto("http://localhost:8765/people")
    
    # Verify hint is visible
    hint = page.locator("#people-hint")
    expect(hint).to_be_visible()
    expect(hint).to_contain_text("Track loans and debts")
    
    # Dismiss hint via "X"
    page.locator("#people-hint").get_by_role("button", name="Dismiss").click()
    expect(hint).to_be_hidden()
    
    # Reload and verify it stays hidden
    page.reload()
    expect(page.locator("#people-hint")).to_be_hidden()

def test_va_hint(page: Page):
    ensure_auth(page)
    page.goto("http://localhost:8765/virtual-accounts")
    
    # Verify hint is visible
    hint = page.locator("#va-hint")
    expect(hint).to_be_visible()
    expect(hint).to_contain_text("Pots")
    
    # Dismiss hint
    page.locator("#va-hint").get_by_role("button", name="Dismiss").click()
    expect(hint).to_be_hidden()
    
    # Reload
    page.reload()
    expect(page.locator("#va-hint")).to_be_hidden()

def test_recurring_hint(page: Page):
    ensure_auth(page)
    page.goto("http://localhost:8765/recurring")
    
    # Verify hint is visible
    hint = page.locator("#recurring-hint")
    expect(hint).to_be_visible()
    expect(hint).to_contain_text("Automate salary, subscriptions")
    
    # Dismiss hint
    page.locator("#recurring-hint").get_by_role("button", name="Dismiss").click()
    expect(hint).to_be_hidden()
    
    # Reload
    page.reload()
    expect(page.locator("#recurring-hint")).to_be_hidden()

def test_hint_hidden_when_data_exists(page: Page):
    user_id = reset_database()
    ensure_auth(page, user_id=user_id)
    
    # Add a person via API or UI
    page.goto("http://localhost:8765/people")
    page.get_by_placeholder("Person name...").fill("John Doe")
    with page.expect_response(
        lambda r: "/people/add" in r.url and r.request.method == "POST"
    ):
        page.get_by_role("button", name="Add", exact=True).click()
    expect(page.locator("#people-list")).to_contain_text("John Doe")
    
    # Reload page
    page.goto("http://localhost:8765/people")
    
    # Hint should not be rendered because data.persons is not empty
    expect(page.locator("#people-hint")).to_be_hidden()
