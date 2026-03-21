"""Auth tests — magic link login, registration, session lifecycle.

Converts: 01-auth.spec.ts + 18-auth.spec.ts
"""
import re
import secrets
import time
from datetime import datetime, timedelta, timezone

import pytest
from playwright.sync_api import Page, expect

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from conftest import (
    TEST_EMAIL,
    _conn,
    create_auth_token,
    ensure_auth,
    reset_database,
)


# ── Module-level DB reset ─────────────────────────────────────────────────────

@pytest.fixture(scope="module", autouse=True)
def db() -> None:
    """Fresh DB for the entire auth test module."""
    reset_database()


@pytest.fixture(autouse=True)
def clear_cookies(page: Page) -> None:
    """Clear cookies before each test so sessions don't bleed between tests."""
    page.context.clear_cookies()


# ── Helper: submit a form with timing bypass ──────────────────────────────────

def _submit_auth_form(page: Page, email: str, action: str = "login") -> None:
    """Fill the auth form and wait 2.5 s before submitting.

    The server checks the _rt (render time) field — forms submitted in under
    2.5 s are rejected as bot activity. Tests must wait before clicking submit.
    """
    page.goto(f"/{action}")
    page.fill('input[name="email"]', email)
    time.sleep(2.5)
    page.click('button[type="submit"]')


# ── Basic auth (from 01-auth.spec.ts) ─────────────────────────────────────────

class TestBasicAuth:
    def test_unauthenticated_redirects_to_login(self, page: Page) -> None:
        page.goto("/")
        expect(page).to_have_url(re.compile(r"/login"))

    def test_login_form_renders(self, page: Page) -> None:
        page.goto("/login")
        expect(page.locator('input[name="email"]')).to_be_visible()
        expect(page.locator('button[type="submit"]')).to_be_visible()

    def test_register_form_renders(self, page: Page) -> None:
        page.goto("/register")
        expect(page.locator('input[name="email"]')).to_be_visible()
        expect(page.locator('button[type="submit"]')).to_be_visible()

    def test_submit_login_shows_check_email(self, page: Page) -> None:
        _submit_auth_form(page, TEST_EMAIL, "login")
        expect(page.locator("main")).to_contain_text("Check your email")

    def test_valid_magic_link_logs_in(self, page: Page) -> None:
        token = create_auth_token(TEST_EMAIL, "login")
        page.goto(f"/auth/verify?token={token}")
        expect(page).to_have_url(re.compile(r"^http://localhost:8001/$"))

    def test_invalid_token_shows_link_expired(self, page: Page) -> None:
        page.goto("/auth/verify?token=notarealtoken")
        expect(page.locator("main")).to_contain_text("Link expired")

    def test_logout_clears_session(self, page: Page) -> None:
        ensure_auth(page)
        page.goto("/")
        page.request.post("/logout")
        page.goto("/")
        expect(page).to_have_url(re.compile(r"/login"))

    @pytest.mark.parametrize("path", ["/accounts", "/transactions", "/reports"])
    def test_protected_routes_reject_unauthenticated(self, page: Page, path: str) -> None:
        page.goto(path)
        expect(page).to_have_url(re.compile(r"/login"))


# ── Page rendering (from 18-auth.spec.ts describe "Page Rendering") ───────────

class TestPageRendering:
    def test_login_page_has_honeypot_field(self, page: Page) -> None:
        page.goto("/login")
        # Anti-bot honeypot: must be present but hidden
        expect(page.locator('input[name="website"]')).to_have_count(1)

    def test_login_page_has_timing_field(self, page: Page) -> None:
        page.goto("/login")
        expect(page.locator('input[name="_rt"]')).to_have_count(1)

    def test_register_page_has_honeypot_field(self, page: Page) -> None:
        page.goto("/register")
        expect(page.locator('input[name="website"]')).to_have_count(1)


# ── Login flow (from 18-auth.spec.ts describe "Login Flow") ───────────────────

class TestLoginFlow:
    def test_valid_email_shows_check_email(self, page: Page) -> None:
        _submit_auth_form(page, TEST_EMAIL, "login")
        expect(page.locator("main")).to_contain_text("Check your email")

    def test_unknown_email_also_shows_check_email(self, page: Page) -> None:
        # Enumeration prevention — unknown email looks identical to valid one
        _submit_auth_form(page, "nobody@example.com", "login")
        expect(page.locator("main")).to_contain_text("Check your email")

    def test_empty_email_shows_validation_error(self, page: Page) -> None:
        page.goto("/login")
        time.sleep(2.5)
        page.click('button[type="submit"]')
        expect(page).to_have_url(re.compile(r"/login"))
        expect(page.locator("main")).to_contain_text("email")


# ── Registration flow (from 18-auth.spec.ts describe "Registration Flow") ─────

class TestRegistrationFlow:
    def test_new_email_shows_check_email(self, page: Page) -> None:
        _submit_auth_form(page, "newuser@example.com", "register")
        expect(page.locator("main")).to_contain_text("Check your email")

    def test_existing_email_shows_error(self, page: Page) -> None:
        # TEST_EMAIL was created by reset_database()
        _submit_auth_form(page, TEST_EMAIL, "register")
        expect(page.locator("main")).to_contain_text("already exists")


# ── Magic link verification (from 18-auth.spec.ts describe "Verification") ────

class TestMagicLinkVerification:
    def test_valid_token_creates_session_and_redirects(self, page: Page) -> None:
        token = create_auth_token(TEST_EMAIL, "login")
        page.goto(f"/auth/verify?token={token}")
        expect(page).to_have_url(re.compile(r"^http://localhost:8001/$"))

    def test_expired_token_shows_link_expired(self, page: Page) -> None:
        token = secrets.token_urlsafe(32)
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO auth_tokens (token, email, purpose, expires_at)"
                    " VALUES (%s, %s, 'login', %s)",
                    (token, TEST_EMAIL, past),
                )
            conn.commit()
        page.goto(f"/auth/verify?token={token}")
        expect(page.locator("main")).to_contain_text("Link expired")

    def test_used_token_shows_link_expired(self, page: Page) -> None:
        token = create_auth_token(TEST_EMAIL, "login")
        # Use it once
        page.goto(f"/auth/verify?token={token}")
        expect(page).to_have_url(re.compile(r"^http://localhost:8001/$"))
        # Clear and try again
        page.context.clear_cookies()
        page.goto(f"/auth/verify?token={token}")
        expect(page.locator("main")).to_contain_text("Link expired")

    def test_missing_token_shows_link_expired(self, page: Page) -> None:
        page.goto("/auth/verify")
        expect(page.locator("main")).to_contain_text("Link expired")

    def test_invalid_token_shows_link_expired(self, page: Page) -> None:
        page.goto("/auth/verify?token=completelywrong")
        expect(page.locator("main")).to_contain_text("Link expired")

    def test_registration_verify_seeds_categories(self, page: Page) -> None:
        """Verifying a register token should seed 25 system categories."""
        token = create_auth_token("brand-new@example.com", "registration")
        page.goto(f"/auth/verify?token={token}")
        expect(page).to_have_url(re.compile(r"^http://localhost:8001/$"))
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM users WHERE email = %s", ("brand-new@example.com",))
                row = cur.fetchone()
                assert row is not None
                cur.execute("SELECT COUNT(*) FROM categories WHERE user_id = %s", (str(row[0]),))
                count_row = cur.fetchone()
                assert count_row is not None
                assert count_row[0] == 25


# ── Logout ────────────────────────────────────────────────────────────────────

class TestLogout:
    def test_logout_clears_session_and_redirects(self, page: Page) -> None:
        ensure_auth(page)
        page.goto("/")
        expect(page).to_have_url(re.compile(r"^http://localhost:8001/$"))
        page.request.post("/logout")
        page.goto("/")
        expect(page).to_have_url(re.compile(r"/login"))


# ── Session continuity ────────────────────────────────────────────────────────

class TestSessionContinuity:
    def test_session_works_across_pages(self, page: Page) -> None:
        ensure_auth(page)
        page.goto("/")
        expect(page).to_have_url(re.compile(r"^http://localhost:8001/$"))
        page.goto("/settings")
        expect(page).to_have_url(re.compile(r"/settings"))
        expect(page.locator("main")).to_be_visible()
