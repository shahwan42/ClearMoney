"""Tests verifying dark mode CSS rules in static/css/app.css.

These act as regression guards — if a dark mode rule is removed or broken,
the test fails and the developer must fix the CSS, not just the test.
"""

import os

CSS_PATH = os.path.join(os.path.dirname(__file__), "../../../static/css/app.css")
CHARTS_CSS_PATH = os.path.join(
    os.path.dirname(__file__), "../../../static/css/charts.css"
)


def read_css(path: str) -> str:
    with open(path) as f:
        return f.read()


class TestDarkModeFormRules:
    """Dark mode CSS must have rules for all interactive form elements."""

    def test_placeholder_dark_mode_rule_exists(self) -> None:
        """Placeholder text needs explicit dark color — browser default is too light."""
        css = read_css(CSS_PATH)
        assert "::placeholder" in css, "Missing ::placeholder dark mode rule in app.css"
        assert ".dark" in css  # redundant but clear intent

    def test_disabled_input_dark_mode_rule_exists(self) -> None:
        """Disabled inputs need a distinct dark mode appearance."""
        css = read_css(CSS_PATH)
        assert ":disabled" in css, "Missing :disabled dark mode rule in app.css"

    def test_red_text_dark_mode_override(self) -> None:
        """text-red-600 (#dc2626) on slate-800 is only 2.6:1 — must be overridden.
        red-400 (#f87171) achieves ~3.6:1 which passes non-text contrast (3:1)."""
        css = read_css(CSS_PATH)
        assert ".dark .text-red-600" in css, (
            "Missing .dark .text-red-600 override — #dc2626 fails WCAG contrast on dark bg"
        )

    def test_green_text_dark_mode_override(self) -> None:
        """text-green-600 (#16a34a) on slate-800 is ~3.7:1 — fails text contrast (4.5:1).
        emerald-400 (#34d399) achieves 5.0:1."""
        css = read_css(CSS_PATH)
        assert ".dark .text-green-600" in css, (
            "Missing .dark .text-green-600 override — #16a34a fails 4.5:1 text contrast on dark bg"
        )

    def test_chart_css_has_custom_properties(self) -> None:
        """charts.css must define CSS custom properties for chart colors."""
        css = read_css(CHARTS_CSS_PATH)
        assert ":root" in css
        assert "--chart-1" in css
        assert ".dark" in css
        assert "#2dd4bf" in css  # teal-400 dark mode color
