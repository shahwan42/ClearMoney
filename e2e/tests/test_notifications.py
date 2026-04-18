"""E2E tests for the notification center.

Covers: bell icon in header, unread badge, notifications list page,
mark-as-read, mark-all-as-read, empty state, data isolation.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from playwright.sync_api import Page, expect
from conftest import (
    _conn,
    ensure_auth,
    reset_database,
)

_user_id: str = ""


@pytest.fixture(scope="function", autouse=True)
def db() -> None:
    global _user_id
    _user_id = reset_database()


@pytest.fixture(autouse=True)
def auth(db: None, page: Page) -> None:
    ensure_auth(page)


def _seed_notification(
    user_id: str,
    title: str,
    body: str,
    tag: str,
    url: str = "/budgets",
    is_read: bool = False,
) -> str:
    """Insert a notification directly into the DB. Returns its UUID string."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO notifications (user_id, title, body, url, tag, is_read)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (user_id, title, body, url, tag, is_read),
            )
            row = cur.fetchone()
            assert row is not None
            return str(row[0])
        conn.commit()


class TestBellIcon:
    def test_bell_icon_visible_on_dashboard(self, page: Page) -> None:
        page.goto("/")
        bell = page.locator('a[href="/notifications"]').first
        expect(bell).to_be_visible()

    def test_bell_icon_visible_on_accounts_page(self, page: Page) -> None:
        page.goto("/accounts")
        bell = page.locator('a[href="/notifications"]').first
        expect(bell).to_be_visible()

    def test_bell_icon_links_to_notifications(self, page: Page) -> None:
        page.goto("/")
        page.locator('a[href="/notifications"]').first.click()
        expect(page).to_have_url("/notifications")


class TestUnreadBadge:
    def test_badge_shown_when_unread_notifications_exist(self, page: Page) -> None:
        _seed_notification(_user_id, "Budget Alert", "Over budget", "badge-t1")
        page.goto("/")
        badge = page.locator("#notification-badge-container .bg-red-500")
        expect(badge).to_be_visible()
        expect(badge).to_contain_text("1")

    def test_badge_not_shown_when_no_unread(self, page: Page) -> None:
        # No notifications seeded
        page.goto("/")
        badge = page.locator("#notification-badge-container .bg-red-500")
        expect(badge).not_to_be_visible()

    def test_badge_shows_correct_count(self, page: Page) -> None:
        _seed_notification(_user_id, "Alert 1", "Body 1", "badge-t2")
        _seed_notification(_user_id, "Alert 2", "Body 2", "badge-t3")
        _seed_notification(_user_id, "Alert 3", "Body 3", "badge-t4", is_read=True)
        page.goto("/")
        badge = page.locator("#notification-badge-container .bg-red-500")
        expect(badge).to_contain_text("2")


class TestNotificationsListPage:
    def test_empty_state_shown_when_no_notifications(self, page: Page) -> None:
        page.goto("/notifications")
        expect(page.locator("body")).to_contain_text("No notifications yet")

    def test_unread_notification_appears_with_teal_border(self, page: Page) -> None:
        _seed_notification(_user_id, "Unread Alert", "This is unread", "list-t1")
        page.goto("/notifications")
        expect(page.locator("body")).to_contain_text("Unread Alert")
        expect(page.locator("body")).to_contain_text("This is unread")
        # Unread cards have teal left border
        card = page.locator(".border-teal-500").first
        expect(card).to_be_visible()

    def test_read_notification_in_earlier_section(self, page: Page) -> None:
        _seed_notification(_user_id, "Read Alert", "This was read", "list-t2", is_read=True)
        page.goto("/notifications")
        expect(page.locator("body")).to_contain_text("Earlier")
        expect(page.locator("body")).to_contain_text("Read Alert")

    def test_mark_all_as_read_button_only_shown_when_unread(self, page: Page) -> None:
        page.goto("/notifications")
        # No notifications — no button
        expect(page.locator("body")).not_to_contain_text("Mark All as Read")

        # Seed one unread notification
        _seed_notification(_user_id, "Alert", "Body", "list-t3")
        page.goto("/notifications")
        expect(page.locator("body")).to_contain_text("Mark All as Read")


class TestMarkRead:
    def test_click_notification_marks_as_read(self, page: Page) -> None:
        notif_id = _seed_notification(
            _user_id, "Budget Over", "Exceeded limit", "mr-t1", url="/budgets"
        )
        page.goto("/notifications")
        # Click the notification card (form submit button that has teal border styling)
        page.locator("button.border-teal-500").first.click()
        # Should redirect to /budgets (the notification URL)
        expect(page).to_have_url("/budgets")

        # Badge should not show after marking as read
        page.goto("/")
        badge = page.locator("#notification-badge-container .bg-red-500")
        expect(badge).not_to_be_visible()

    def test_mark_all_as_read_clears_badge(self, page: Page) -> None:
        _seed_notification(_user_id, "Alert 1", "Body 1", "mar-t1")
        _seed_notification(_user_id, "Alert 2", "Body 2", "mar-t2")
        page.goto("/notifications")
        page.locator("button:has-text('Mark All as Read')").click()
        # After redirect, no unread badge
        page.goto("/")
        badge = page.locator("#notification-badge-container .bg-red-500")
        expect(badge).not_to_be_visible()

    def test_mark_all_as_read_moves_to_earlier_section(self, page: Page) -> None:
        _seed_notification(_user_id, "Alert", "Body", "mar-t3")
        page.goto("/notifications")
        page.locator("button:has-text('Mark All as Read')").click()
        page.goto("/notifications")
        expect(page.locator("body")).to_contain_text("Earlier")
        expect(page.locator("body")).not_to_contain_text("Mark All as Read")


class TestDataIsolation:
    def test_user_cannot_see_other_users_notifications(self, page: Page) -> None:
        # Create a second user with a notification
        with _conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (email, language, created_at) VALUES (%s, 'en', NOW()) RETURNING id",
                    ("other@test.local",),
                )
                row = cur.fetchone()
                assert row is not None
                other_user_id = str(row[0])
            conn.commit()

        _seed_notification(other_user_id, "Other User Secret", "Private", "iso-t1")

        page.goto("/notifications")
        expect(page.locator("body")).not_to_contain_text("Other User Secret")
        expect(page.locator("body")).to_contain_text("No notifications yet")
