"""Tests for Issue 08 — More menu reorganization with grouped sections."""

from django.test import TestCase

from tests.factories import SessionFactory


class MoreMenuGroupingTest(TestCase):
    """Verify More menu has section headers and descriptive subtitles."""

    def setUp(self) -> None:
        session = SessionFactory()
        self.client.cookies["clearmoney_session"] = session.token

    def test_more_menu_has_money_management_section(self) -> None:
        """Section header 'Money Management' appears in bottom nav."""
        resp = self.client.get("/")
        content = resp.content.decode()
        assert "Money Management" in content

    def test_more_menu_has_automation_section(self) -> None:
        """Section header 'Automation' appears in bottom nav."""
        resp = self.client.get("/")
        content = resp.content.decode()
        assert "Automation" in content

    def test_more_menu_has_descriptive_subtitles(self) -> None:
        """Menu items have descriptive subtitle text."""
        resp = self.client.get("/")
        content = resp.content.decode()
        assert "Track loans and debts" in content
        assert "Monthly spending limits" in content
        assert "Set money aside for goals" in content
        assert "Auto-create transactions" in content

    def test_more_menu_includes_reports_link(self) -> None:
        """Reports link is present in the More menu."""
        resp = self.client.get("/")
        content = resp.content.decode()
        assert 'href="/reports"' in content
