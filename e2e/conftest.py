"""E2E test fixtures and helpers — replaces playwright.config.ts + helpers.ts.

Design notes:
- django_server: session-scoped, starts manage.py runserver once per pytest run.
- reset_database(): module-level DB wipe called from each test module's autouse fixture.
- All DB ops use psycopg directly (no execSync psql shelling like the old JS helpers).
- API helpers use page.request so auth cookies are included automatically.
"""

import json
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
        # Not running or unhealthy — kill any stale process holding the port
        # before starting a new one, otherwise the new server can't bind.
        result = subprocess.run(
            ["lsof", "-ti", ":8765"],
            capture_output=True,
            text=True,
        )
        if result.stdout.strip():
            for pid in result.stdout.strip().split("\n"):
                subprocess.run(["kill", "-9", pid], capture_output=True)
            time.sleep(1)  # Let the port release

    env = {
        **os.environ,
        "DISABLE_RATE_LIMIT": "true",
        "DATABASE_URL": DB_URL,
        "DJANGO_SETTINGS_MODULE": "clearmoney.settings",
    }
    _repair_partial_currency_migration_state()
    migrate = subprocess.run(
        ["uv", "run", "python", "manage.py", "migrate", "--noinput"],
        cwd=os.path.join(_BASE_DIR, "backend"),
        env=env,
        capture_output=True,
        text=True,
    )
    if migrate.returncode != 0:
        raise RuntimeError(
            "Django migrations failed before E2E startup:\n"
            f"{migrate.stdout}\n{migrate.stderr}"
        )

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


def _repair_partial_currency_migration_state() -> None:
    """Remove half-applied auth_app 0007 artifacts before running migrations."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM django_migrations
                WHERE app = 'auth_app' AND name = '0007_currency_registry_and_preferences'
                LIMIT 1
                """
            )
            if cur.fetchone() is not None:
                conn.commit()
                return
            cur.execute("DROP TABLE IF EXISTS user_currency_preferences CASCADE")
            cur.execute("DROP TABLE IF EXISTS currencies CASCADE")
        conn.commit()


def reset_database() -> str:
    """Truncate all user tables, create the test user, seed 25 categories.

    Returns the test user's UUID string.
    Equivalent to helpers.ts resetDatabase().
    """
    # Terminate idle connections to avoid lock contention during TRUNCATE.
    # Django reconnects automatically via CONN_HEALTH_CHECKS.
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = current_database()
                  AND pid <> pg_backend_pid()
                  AND state = 'idle'
            """)
        conn.commit()

    with _conn() as conn:
        with conn.cursor() as cur:
            # Wipe all user-owned data in dependency order (matches actual schema)
            cur.execute("""
                TRUNCATE TABLE
                    notifications,
                    budgets, virtual_account_allocations, virtual_accounts,
                    account_snapshots, daily_snapshots, transactions,
                    accounts, institutions, categories, persons,
                    recurring_rules, investments,
                    user_currency_preferences,
                    sessions, auth_tokens, user_config, users
                RESTART IDENTITY CASCADE
            """)
            # exchange_rate_log has no user_id — truncate separately
            cur.execute("TRUNCATE TABLE exchange_rate_log RESTART IDENTITY CASCADE")

            cur.execute(
                "INSERT INTO users (email, language, created_at) VALUES (%s, 'en', NOW()) RETURNING id",
                (TEST_EMAIL,),
            )
            row = cur.fetchone()
            assert row is not None
            user_id: str = str(row[0])

            cur.execute(
                "SELECT code FROM currencies WHERE is_enabled = TRUE ORDER BY display_order, code"
            )
            active_currency_codes = [str(row[0]) for row in cur.fetchall()]
            if not active_currency_codes:
                active_currency_codes = ["EGP"]
            selected_display_currency = (
                "EGP"
                if "EGP" in active_currency_codes
                else active_currency_codes[0]
            )
            cur.execute(
                "INSERT INTO user_currency_preferences"
                " (user_id, active_currency_codes, selected_display_currency)"
                " VALUES (%s, %s, %s)",
                (
                    user_id,
                    json.dumps(active_currency_codes),
                    selected_display_currency,
                ),
            )

            expense_categories = [
                "Food & Dining",
                "Transportation",
                "Shopping",
                "Entertainment",
                "Health & Fitness",
                "Bills & Utilities",
                "Travel",
                "Education",
                "Personal Care",
                "Home",
                "Gifts & Donations",
                "Business",
                "Fees & Charges",
                "Taxes",
                "Other Expenses",
            ]
            income_categories = [
                "Salary",
                "Freelance",
                "Investments",
                "Rental Income",
                "Gifts",
                "Refunds",
                "Business Income",
                "Other Income",
                "Cashback",
                "Bonus",
            ]
            for name in expense_categories:
                cur.execute(
                    "INSERT INTO categories (user_id, name, type) VALUES (%s, %s, 'expense')",
                    (user_id, json.dumps({"en": name})),
                )
            for name in income_categories:
                cur.execute(
                    "INSERT INTO categories (user_id, name, type) VALUES (%s, %s, 'income')",
                    (user_id, json.dumps({"en": name})),
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
            assert row is not None, (
                f"No {category_type} category found for user {user_id}"
            )
            return str(row[0])


def ensure_auth(page: Page, user_id: str | None = None) -> str:
    """Create a 30-day session in DB and inject the cookie into the page context.

    Args:
        page: Playwright page object
        user_id: Explicit user ID to create session for (for testing). If None, looks up TEST_EMAIL.

    Returns: The session token

    Equivalent to helpers.ts ensureAuth().
    """
    if user_id is None:
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM users WHERE email = %s", (TEST_EMAIL,))
                row = cur.fetchone()
                assert row is not None, (
                    f"Test user {TEST_EMAIL} not found — call reset_database() first"
                )
                user_id = str(row[0])

    token = secrets.token_urlsafe(32)
    expiry = datetime.now(timezone.utc) + timedelta(days=30)
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sessions (token, user_id, expires_at) VALUES (%s, %s, %s)",
                (token, user_id, expiry),
            )
        conn.commit()
    page.context.add_cookies(
        [
            {
                "name": "clearmoney_session",
                "value": token,
                "domain": "localhost",
                "path": "/",
            }
        ]
    )
    return token


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
    payload = {"name": name, "type": inst_type}
    resp = page.request.post(
        "/api/institutions",
        data=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )
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
    resp = page.request.post(
        "/api/accounts",
        data=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )
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
    resp = page.request.post(
        "/api/transactions",
        data=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )
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
