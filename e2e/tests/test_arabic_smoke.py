"""Arabic locale smoke test — #518.

Switches the test user's language to Arabic, walks 8 key pages,
asserts <html lang="ar" dir="rtl"> and that no major English fallback
strings leak through. Captures screenshots under e2e/screenshots/ar/.

Allowlist (English literals that may legitimately appear in Arabic UI):
- Brand names: ClearMoney, CIB, NBE, HSBC, etc.
- Numbers, currency codes (EGP, USD, ...).
- The user's own data (account names, notes — these are user-entered).
"""

import os
import sys

import psycopg
import pytest
from playwright.sync_api import Page, expect

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from conftest import DB_URL, TEST_EMAIL, ensure_auth, reset_database  # noqa: E402

SCREENSHOTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "screenshots", "ar"
)
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

# Pages to walk + path → label for screenshots
PAGES = [
    ("/", "home"),
    ("/transactions", "transactions"),
    ("/accounts", "accounts"),
    ("/budgets", "budgets"),
    ("/settings", "settings"),
    ("/recurring", "recurring"),
    ("/reports", "reports"),
    ("/people", "people"),
]

# English fallback indicators — common UI strings that should be Arabic now.
# Keep this list small and surgical; user-entered data and brand names are OK.
ENGLISH_LEAKS = [
    "Loading...",
    "Cancel",
    "Save",
    "Settings",
    "Reports",
    "Recurring",
    "Accounts",
    "Budgets",
]


@pytest.fixture(scope="function", autouse=True)
def db() -> None:
    reset_database()


@pytest.fixture(autouse=True)
def auth(db: None, page: Page) -> None:
    ensure_auth(page)
    # Switch user to Arabic directly in DB to avoid race-y form submit
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET language = 'ar' WHERE email = %s", (TEST_EMAIL,)
            )
        conn.commit()


class TestArabicSmoke:
    def test_html_lang_and_dir_on_home(self, page: Page) -> None:
        page.goto("/")
        page.wait_for_load_state("networkidle")
        html = page.locator("html")
        expect(html).to_have_attribute("lang", "ar")
        expect(html).to_have_attribute("dir", "rtl")

    @pytest.mark.parametrize("path,label", PAGES)
    def test_page_renders_in_arabic(self, page: Page, path: str, label: str) -> None:
        """Each page renders with lang=ar dir=rtl and no major English leaks."""
        page.goto(path)
        page.wait_for_load_state("networkidle")
        html = page.locator("html")
        expect(html).to_have_attribute("lang", "ar")
        expect(html).to_have_attribute("dir", "rtl")

        # Snapshot for visual review
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, f"{label}.png"))

        # Check <main> for known English fallbacks. Allow brand names and
        # user data via the small ENGLISH_LEAKS list — only fail on these.
        main = page.locator("main")
        expect(main).to_be_visible()
        main_text = main.inner_text(timeout=5000)
        leaks = [s for s in ENGLISH_LEAKS if s in main_text]
        assert not leaks, (
            f"English fallback strings present on {path}: {leaks}\n"
            f"This means the .po file is missing translations for these msgids."
        )
