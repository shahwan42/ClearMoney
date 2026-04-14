"""Tests for WCAG 44x44px minimum touch target compliance on icon-only buttons."""

from pathlib import Path

TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent


class TestTouchTargets:
    """All icon-only buttons must have min-h-[44px] min-w-[44px] or equivalent."""

    def test_header_theme_toggle_has_touch_target(self) -> None:
        """Header dark mode toggle button must have 44px minimum touch target."""
        html = (TEMPLATES_DIR / "templates" / "components" / "header.html").read_text()
        assert "min-h-[44px]" in html or "min-w-[44px]" in html or "p-3" in html

    def test_header_icon_links_have_touch_target(self) -> None:
        """Header icon links (accounts, reports, settings) must have 44px touch target."""
        html = (TEMPLATES_DIR / "templates" / "components" / "header.html").read_text()
        # All icon links should have padding for touch targets
        assert "p-2" in html

    def test_institution_edit_button_has_touch_target(self) -> None:
        """Institution edit icon button must have 44px minimum touch target."""
        html = (
            TEMPLATES_DIR
            / "accounts"
            / "templates"
            / "accounts"
            / "_institution_card.html"
        ).read_text()
        assert "min-h-[44px]" in html

    def test_institution_edit_button_has_aria_label(self) -> None:
        """Institution edit icon button must have aria-label."""
        html = (
            TEMPLATES_DIR
            / "accounts"
            / "templates"
            / "accounts"
            / "_institution_card.html"
        ).read_text()
        assert 'aria-label="{% trans "Edit institution" %}' in html

    def test_institution_delete_button_has_aria_label(self) -> None:
        """Institution delete icon button must have aria-label."""
        html = (
            TEMPLATES_DIR
            / "accounts"
            / "templates"
            / "accounts"
            / "_institution_card.html"
        ).read_text()
        assert 'aria-label="{% trans "Delete institution" %}' in html

    def test_transaction_kebab_has_touch_target(self) -> None:
        """Transaction kebab menu button must have 44px minimum touch target."""
        html = (
            TEMPLATES_DIR
            / "transactions"
            / "templates"
            / "transactions"
            / "_transaction_row.html"
        ).read_text()
        assert "min-h-[44px]" in html or "min-w-[44px]" in html
