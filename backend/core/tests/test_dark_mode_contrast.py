"""Tests for dark mode contrast compliance.

Verifies that the CSS includes overrides for WCAG AA contrast on dark backgrounds.
teal-600 (#0d9488) on slate-800 (#1e293b) fails at 3.6:1 — needs teal-400 (#2dd4bf).
"""

from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parent.parent.parent.parent / "static"


class TestDarkModeTealContrast:
    """Ensure teal-600 text is overridden to teal-400 in dark mode for WCAG AA."""

    def test_css_has_dark_teal_600_override(self) -> None:
        """app.css must override .text-teal-600 in dark mode to teal-400."""
        css = (STATIC_DIR / "css" / "app.css").read_text()
        assert ".dark .text-teal-600" in css
        # teal-400 = #2dd4bf
        assert "#2dd4bf" in css

    def test_css_has_dark_amount_positive_override(self) -> None:
        """app.css must override .amount-positive in dark mode."""
        css = (STATIC_DIR / "css" / "app.css").read_text()
        assert ".dark .amount-positive" in css

    def test_css_has_dark_hover_teal_700_override(self) -> None:
        """app.css must override hover:text-teal-700 in dark mode."""
        css = (STATIC_DIR / "css" / "app.css").read_text()
        assert ".dark .hover\\:text-teal-700:hover" in css

    def test_theme_js_respects_os_preference(self) -> None:
        """theme.js must check prefers-color-scheme for first-time visitors."""
        js = (STATIC_DIR / "js" / "theme.js").read_text()
        assert "prefers-color-scheme" in js

    def test_settings_toggle_updates_state(self) -> None:
        """theme.js must update the settings page toggle button state."""
        js = (STATIC_DIR / "js" / "theme.js").read_text()
        assert "settings-theme-toggle" in js or "settings-theme-label" in js
