import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from playwright.sync_api import Page, expect

from conftest import (
    ensure_auth,
    reset_database,
    seed_basic_data,
    create_transaction,
    get_category_id,
)

_user_id: str = ""

@pytest.fixture(scope="function", autouse=True)
def db() -> None:
    global _user_id
    _user_id = reset_database()

@pytest.fixture(autouse=True)
def auth(db: None, page: Page) -> None:
    ensure_auth(page)

@pytest.fixture(scope="function")
def browser_context_args(browser_context_args: dict) -> dict:
    """Enable touch support for gesture tests."""
    return {
        **browser_context_args,
        "has_touch": True,
    }

def test_pull_to_refresh_only_at_top(page: Page) -> None:
    """Verify that pull-to-refresh only triggers when scrolled to the very top."""
    # 1. Seed enough data to make the page scrollable
    inst_id, acc_id = seed_basic_data(page)
    cat_id = get_category_id("expense", _user_id)
    
    # Add many transactions to ensure scrolling
    for i in range(20):
        create_transaction(page, acc_id, cat_id, "10", "expense", note=f"Tx {i}")
        
    page.goto("/", wait_until="networkidle")
    
    # 2. Verify we can scroll
    page.evaluate("document.getElementById('main-content').scrollTop = 200")
    scroll_top = page.evaluate("document.getElementById('main-content').scrollTop")
    assert scroll_top >= 200
    
    # 3. Try to pull to refresh while scrolled down
    # Set a marker to detect reload
    page.evaluate("window.isNotReloaded = true")
    
    # Simulate touch pull while scrolled down
    page.evaluate("""() => {
        const el = document.querySelector('[data-pull-refresh]');
        const dispatchTouch = (type, y) => {
            const touch = new Touch({
                identifier: Date.now(),
                target: el,
                clientY: y,
                clientX: 200,
                radiusX: 2.5,
                radiusY: 2.5,
                force: 0.5,
            });
            const event = new TouchEvent(type, {
                cancelable: true,
                bubbles: true,
                touches: [touch],
                targetTouches: [touch],
                changedTouches: [touch],
            });
            el.dispatchEvent(event);
        };
        
        dispatchTouch('touchstart', 300);
        dispatchTouch('touchmove', 500);
        dispatchTouch('touchend', 500);
    }""")
    
    # Wait a bit
    page.wait_for_timeout(500)
    
    # Verify NO reload happened
    is_not_reloaded = page.evaluate("window.isNotReloaded")
    assert is_not_reloaded is True, "Page reloaded unexpectedly while scrolled down"
    
    # Verify NO pull indicator is visible
    indicator_count = page.evaluate("document.querySelectorAll('.animate-fade-in').length")
    assert indicator_count == 0, "Pull indicator appeared while scrolled down"

def test_pull_to_refresh_works_at_top(page: Page) -> None:
    """Verify that pull-to-refresh triggers when at the top."""
    seed_basic_data(page)
    page.goto("/", wait_until="networkidle")
    
    # Ensure at top
    page.evaluate("document.getElementById('main-content').scrollTop = 0")
    
    # Set a marker to detect reload
    page.evaluate("window.isNotReloaded = true")
    
    # Simulate touch pull: start at y=150, move to y=400 (250px pull)
    # Note: we need to use actual touch events if possible, or simulate them
    # Playwright's mouse events might not trigger 'touchstart'/'touchmove' listeners 
    # if the browser isn't in touch mode or if listeners only listen to touch.
    
    # Let's use dispatchEvent for reliability in simulation
    page.evaluate("""() => {
        const el = document.querySelector('[data-pull-refresh]');
        const dispatchTouch = (type, y) => {
            const touch = new Touch({
                identifier: Date.now(),
                target: el,
                clientY: y,
                clientX: 200,
                radiusX: 2.5,
                radiusY: 2.5,
                rotationAngle: 10,
                force: 0.5,
            });
            const event = new TouchEvent(type, {
                cancelable: true,
                bubbles: true,
                touches: [touch],
                targetTouches: [touch],
                changedTouches: [touch],
            });
            el.dispatchEvent(event);
        };
        
        dispatchTouch('touchstart', 150);
        setTimeout(() => dispatchTouch('touchmove', 400), 50);
        setTimeout(() => dispatchTouch('touchend', 400), 100);
    }""")
    
    # Wait for reload (it should happen)
    # If it reloads, window.isNotReloaded will be gone
    reloaded = False
    for _ in range(50):
        try:
            val = page.evaluate("window.isNotReloaded")
            if val is None:
                reloaded = True
                break
        except:
            # Page might be in transition
            reloaded = True
            break
        time.sleep(0.1)
        
    assert reloaded, "Page did not reload when pulling from the top"
