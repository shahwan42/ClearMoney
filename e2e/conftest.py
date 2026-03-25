"""E2E test fixtures and helpers — replaces playwright.config.ts + helpers.ts.

Design notes:
- django_server: session-scoped, starts manage.py runserver once per pytest run.
- reset_database(): module-level DB wipe called from each test module's autouse fixture.
- All DB ops use psycopg directly (no execSync psql shelling like the old JS helpers).
- API helpers use page.request so auth cookies are included automatically.
"""
import os
import secrets
import subprocess
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Generator

import psycopg
import pytest
from playwright.sync_api import Page

# ── Constants ─────────────────────────────────────────────────────────────────

DB_URL: str = os.getenv(
    "DATABASE_URL",
    "postgres://clearmoney:clearmoney@localhost:5433/clearmoney",
)
TEST_EMAIL: str = "test@clearmoney.local"
_BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── Browser configuration (replaces playwright.config.ts project settings) ───

@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict) -> dict:
    """Mobile viewport + en-US locale + service workers blocked."""
    return {
        **browser_context_args,
        "viewport": {"width": 430, "height": 932},
        "locale": "en-US",
        "service_workers": "block",
    }


_DISABLE_ANIMATIONS_SCRIPT = """
(() => {
    // Inject a <style> that zeroes all CSS transitions/animations as soon as
    // <head> exists.  This prevents "element not stable" flakiness in tests
    // that interact with animated containers (e.g. bottom sheets).
    function inject() {
        var s = document.createElement('style');
        s.textContent = '*, *::before, *::after { ' +
            'transition-duration: 0ms !important; ' +
            'transition-delay: 0ms !important; ' +
            'animation-duration: 0ms !important; ' +
            'animation-delay: 0ms !important; }';
        document.head.insertBefore(s, document.head.firstChild);
    }
    if (document.head) {
        inject();
    } else {
        new MutationObserver(function(_, obs) {
            if (document.head) { inject(); obs.disconnect(); }
        }).observe(document.documentElement, { childList: true, subtree: true });
    }
})();
"""


@pytest.fixture(autouse=True)
def _disable_animations(page: Page) -> None:
    """Disable CSS transitions/animations so Playwright stability checks pass instantly."""
    page.add_init_script(_DISABLE_ANIMATIONS_SCRIPT)


# ── Django dev server (replaces playwright.config.ts webServer) ───────────────

@pytest.fixture(scope="session", autouse=True)
def django_server() -> Generator[None, None, None]:
    """Spawn Django runserver on :8000 with rate limiting disabled.

    Polls /healthz until ready (max 30 s), then yields for the test session.
    Mirrors the webServer block in playwright.config.ts.
    """
    # If a healthy clearmoney server is already running, reuse it.
    try:
        with urllib.request.urlopen("http://localhost:8765/healthz", timeout=5) as resp:
            if resp.status == 200:
                yield
                return
    except OSError:
        pass  # Not running or unhealthy — start one below

    env = {
        **os.environ,
        "DISABLE_RATE_LIMIT": "true",
        "DATABASE_URL": DB_URL,
        "DJANGO_SETTINGS_MODULE": "clearmoney.settings",
    }
    proc = subprocess.Popen(
        ["uv", "run", "python", "manage.py", "runserver", "--noreload", "0.0.0.0:8765"],
        cwd=os.path.join(_BASE_DIR, "backend"),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(30):
        try:
            urllib.request.urlopen("http://localhost:8765/healthz")
            break
        except OSError:
            time.sleep(1)
    else:
        proc.terminate()
        raise RuntimeError("Django server did not start within 30 s")

    yield

    proc.terminate()
    proc.wait()


# ── Database helpers (replaces execSync('psql ...') in helpers.ts) ────────────

def _conn() -> psycopg.Connection:
    """Open a new psycopg connection. Caller is responsible for closing."""
    return psycopg.connect(DB_URL)


def reset_database() -> str:
    """Truncate all user tables, create the test user, seed 25 categories.

    Returns the test user's UUID string.
    Equivalent to helpers.ts resetDatabase().
    """
    with _conn() as conn:
        with conn.cursor() as cur:
            # Wipe all user-owned data in dependency order (matches actual schema)
            cur.execute("""
                TRUNCATE TABLE
                    budgets, virtual_account_allocations, virtual_accounts,
                    account_snapshots, daily_snapshots, transactions,
                    accounts, institutions, categories, persons,
                    recurring_rules, investments,
                    sessions, auth_tokens, user_config, users
                RESTART IDENTITY CASCADE
            """)
            # exchange_rate_log has no user_id — truncate separately
            cur.execute("TRUNCATE TABLE exchange_rate_log RESTART IDENTITY CASCADE")

            cur.execute(
                "INSERT INTO users (email, created_at) VALUES (%s, NOW()) RETURNING id",
                (TEST_EMAIL,),
            )
            row = cur.fetchone()
            assert row is not None
            user_id: str = str(row[0])

            expense_categories = [
                "Food & Dining", "Transportation", "Shopping", "Entertainment",
                "Health & Fitness", "Bills & Utilities", "Travel", "Education",
                "Personal Care", "Home", "Gifts & Donations", "Business",
                "Fees & Charges", "Taxes", "Other Expenses",
            ]
            income_categories = [
                "Salary", "Freelance", "Investments", "Rental Income",
                "Gifts", "Refunds", "Business Income", "Other Income",
                "Cashback", "Bonus",
            ]
            for name in expense_categories:
                cur.execute(
                    "INSERT INTO categories (user_id, name, type) VALUES (%s, %s, 'expense')",
                    (user_id, name),
                )
            for name in income_categories:
                cur.execute(
                    "INSERT INTO categories (user_id, name, type) VALUES (%s, %s, 'income')",
                    (user_id, name),
                )
        conn.commit()
    return user_id


def get_category_id(category_type: str, user_id: str) -> str:
    """Return the first category ID of the given type for the user."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM categories WHERE type = %s AND user_id = %s LIMIT 1",
                (category_type, user_id),
            )
            row = cur.fetchone()
            assert row is not None, f"No {category_type} category found for user {user_id}"
            return str(row[0])


def ensure_auth(page: Page) -> None:
    """Create a 30-day session in DB and inject the cookie into the page context.

    Equivalent to helpers.ts ensureAuth().
    """
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email = %s", (TEST_EMAIL,))
            row = cur.fetchone()
            assert row is not None, f"Test user {TEST_EMAIL} not found — call reset_database() first"
            user_id = str(row[0])
            token = secrets.token_urlsafe(32)
            expiry = datetime.now(timezone.utc) + timedelta(days=30)
            cur.execute(
                "INSERT INTO sessions (token, user_id, expires_at) VALUES (%s, %s, %s)",
                (token, user_id, expiry),
            )
        conn.commit()
    page.context.add_cookies([{
        "name": "clearmoney_session",
        "value": token,
        "domain": "localhost",
        "path": "/",
    }])


def create_auth_token(email: str, purpose: str = "login") -> str:
    """Insert a magic link token with 15-min expiry, return the token string."""
    token = secrets.token_urlsafe(32)
    expiry = datetime.now(timezone.utc) + timedelta(minutes=15)
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO auth_tokens (token, email, purpose, expires_at)"
                " VALUES (%s, %s, %s, %s)",
                (token, email, purpose, expiry),
            )
        conn.commit()
    return token


def create_expired_session(user_id: str) -> str:
    """Create a session that expired yesterday (for auth rejection tests)."""
    token = secrets.token_urlsafe(32)
    expiry = datetime.now(timezone.utc) - timedelta(days=1)
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sessions (token, user_id, expires_at) VALUES (%s, %s, %s)",
                (token, user_id, expiry),
            )
        conn.commit()
    return token


# ── API helpers (replaces page.request.post wrappers in helpers.ts) ───────────

def create_institution(page: Page, name: str, inst_type: str = "bank") -> str:
    """POST /api/institutions and return the new institution ID."""
    resp = page.request.post("/api/institutions", data={"name": name, "type": inst_type})
    assert resp.ok, f"create_institution failed: {resp.status} {resp.text()}"
    return str(resp.json()["id"])


def create_account(
    page: Page,
    name: str,
    institution_id: str,
    account_type: str = "current",
    currency: str = "EGP",
    initial_balance: str = "0",
    credit_limit: str | None = None,
) -> str:
    """POST /api/accounts and return the new account ID."""
    payload: dict[str, str] = {
        "name": name,
        "institution_id": institution_id,
        "type": account_type,
        "currency": currency,
        "initial_balance": initial_balance,
    }
    if credit_limit is not None:
        payload["credit_limit"] = credit_limit
    resp = page.request.post("/api/accounts", data=payload)
    assert resp.ok, f"create_account failed: {resp.status} {resp.text()}"
    return str(resp.json()["id"])


def create_transaction(
    page: Page,
    account_id: str,
    category_id: str,
    amount: str,
    tx_type: str,
    note: str = "",
    date: str = "",
) -> str:
    """POST /api/transactions and return the new transaction ID."""
    payload: dict[str, str] = {
        "account_id": account_id,
        "category_id": category_id,
        "amount": amount,
        "type": tx_type,
    }
    if note:
        payload["note"] = note
    if date:
        payload["date"] = date
    resp = page.request.post("/api/transactions", data=payload)
    assert resp.ok, f"create_transaction failed: {resp.status} {resp.text()}"
    # POST /api/transactions returns {"transaction": {...}, "new_balance": X}
    return str(resp.json()["transaction"]["id"])


def seed_basic_data(page: Page) -> tuple[str, str]:
    """Create 'Test Bank' + 'Current' EGP account (EGP 10,000 balance).

    Returns (institution_id, account_id). Equivalent to helpers.ts seedBasicData().
    """
    institution_id = create_institution(page, "Test Bank")
    account_id = create_account(
        page,
        name="Current",
        institution_id=institution_id,
        initial_balance="10000",
    )
    return institution_id, account_id
