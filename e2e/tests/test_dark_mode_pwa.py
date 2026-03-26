"""Dark mode toggle and PWA manifest tests.

Converts: 12-dark-mode-pwa.spec.ts
"""
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from playwright.sync_api import Page, expect
from conftest import ensure_auth, reset_database


@pytest.fixture(scope="function", autouse=True)
def db() -> None:
    reset_database()


@pytest.fixture(autouse=True)
def auth(db: None, page: Page) -> None:
    ensure_auth(page)


class TestDarkMode:
    def test_dark_mode_toggle_adds_dark_class(self, page: Page) -> None:
        page.goto("/settings")
        page.click('button[aria-label="Toggle dark mode"]')
        expect(page.locator("html")).to_have_class(re.compile(r"\bdark\b"))

    def test_dark_mode_toggle_removes_dark_class(self, page: Page) -> None:
        page.goto("/settings")
        # Enable then disable
        page.click('button[aria-label="Toggle dark mode"]')
        page.click('button[aria-label="Toggle dark mode"]')
        expect(page.locator("html")).not_to_have_class(re.compile(r"\bdark\b"))


class TestPWA:
    def test_manifest_link_present(self, page: Page) -> None:
        page.goto("/")
        manifest = page.locator('link[rel="manifest"]')
        expect(manifest).to_have_count(1)

    def test_viewport_meta_tag(self, page: Page) -> None:
        page.goto("/")
        viewport = page.locator('meta[name="viewport"]')
        expect(viewport).to_have_count(1)
