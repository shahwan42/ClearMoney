"""Tests verifying dark mode CSS rules and template coverage.

CSS tests act as regression guards — if a dark mode rule is removed or broken,
the test fails and the developer must fix the CSS, not just the test.

Template tests verify that cards/containers have dark: Tailwind variants so
they don't render as white boxes on a dark slate background.
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


TEMPLATES_BASE = os.path.join(os.path.dirname(__file__), "../../..")


def read_template(rel_path: str) -> str:
    with open(os.path.join(TEMPLATES_BASE, rel_path)) as f:
        return f.read()


class TestDarkModeCardTemplates:
    """Card and container templates must have dark: Tailwind variants.

    White bg-white cards without dark:bg-slate-800 appear as glaring white
    boxes on the dark slate-900 page background — a critical dark mode gap.
    """

    def test_institution_card_has_dark_bg(self) -> None:
        """Institution card (accounts list) must have dark background."""
        html = read_template(
            "backend/accounts/templates/accounts/_institution_card.html"
        )
        assert "dark:bg-slate-800" in html, (
            "_institution_card.html missing dark:bg-slate-800 — white card on dark bg"
        )

    def test_institution_card_text_has_dark_variants(self) -> None:
        """Institution name and type labels need dark text variants."""
        html = read_template(
            "backend/accounts/templates/accounts/_institution_card.html"
        )
        assert "dark:text-slate-100" in html or "dark:text-slate-200" in html, (
            "_institution_card.html missing dark text variants for account names"
        )

    def test_transaction_row_label_has_dark_text(self) -> None:
        """Transaction description text must be visible in dark mode."""
        html = read_template(
            "backend/transactions/templates/transactions/_transaction_row.html"
        )
        assert "dark:text-slate-100" in html or "dark:text-slate-200" in html, (
            "_transaction_row.html missing dark text variant for description label"
        )

    def test_transaction_row_kebab_menu_has_dark_bg(self) -> None:
        """Kebab dropdown must have dark background — white dropdown on dark screen is jarring."""
        html = read_template(
            "backend/transactions/templates/transactions/_transaction_row.html"
        )
        assert "dark:bg-slate-800" in html or "dark:bg-slate-700" in html, (
            "_transaction_row.html kebab dropdown missing dark background"
        )

    def test_virtual_accounts_page_cards_have_dark_bg(self) -> None:
        """Virtual account list cards must have dark background."""
        html = read_template(
            "backend/virtual_accounts/templates/virtual_accounts/virtual_accounts.html"
        )
        assert "dark:bg-slate-800" in html, (
            "virtual_accounts.html missing dark:bg-slate-800 on account cards"
        )

    def test_virtual_accounts_form_section_has_dark_bg(self) -> None:
        """Create VA form section must have dark background."""
        html = read_template(
            "backend/virtual_accounts/templates/virtual_accounts/virtual_accounts.html"
        )
        # Count occurrences — need at least 2 (form section + cards)
        assert html.count("dark:bg-slate-800") >= 2, (
            "virtual_accounts.html needs dark:bg-slate-800 on both form section and cards"
        )

    def test_settings_all_sections_have_dark_bg(self) -> None:
        """All settings page sections must have dark background."""
        html = read_template(
            "backend/settings_app/templates/settings_app/settings.html"
        )
        # Dark Mode, Export, Push Notifications, Categories, Quick Links sections
        assert html.count("dark:bg-slate-800") >= 4, (
            "settings.html needs dark:bg-slate-800 on all 5 sections (Dark Mode, Export already done, "
            "Push Notifications, Categories, Quick Links)"
        )

    def test_accounts_page_heading_has_dark_text(self) -> None:
        """Accounts page heading must be visible in dark mode."""
        html = read_template("backend/accounts/templates/accounts/accounts.html")
        assert "dark:text-slate-100" in html or "dark:text-white" in html, (
            "accounts.html heading missing dark text variant"
        )


class TestDarkModeButtonTemplates:
    """Buttons and interactive elements must have dark: variants or be covered by global CSS."""

    def test_quick_entry_heading_has_dark_text(self) -> None:
        """Quick entry heading (text-slate-800) must be visible in dark mode."""
        html = read_template(
            "backend/transactions/templates/transactions/_quick_entry.html"
        )
        assert "dark:text-slate-100" in html or "dark:text-white" in html, (
            "_quick_entry.html heading missing dark text variant"
        )

    def test_kebab_trigger_button_has_dark_hover(self) -> None:
        """Kebab trigger hover:bg-gray-100 would show a white flash in dark mode."""
        html = read_template(
            "backend/transactions/templates/transactions/_transaction_row.html"
        )
        assert "dark:hover:bg-slate-700" in html or "dark:hover:bg-slate-800" in html, (
            "_transaction_row.html kebab trigger missing dark hover background"
        )

    def test_dormant_button_has_dark_variant(self) -> None:
        """Dormant toggle button (bg-gray-100) needs a dark mode background."""
        html = read_template("backend/accounts/templates/accounts/account_detail.html")
        assert "dark:bg-slate-700" in html or "dark:bg-slate-600" in html, (
            "account_detail.html dormant button missing dark:bg variant"
        )

    def test_css_has_indigo_100_dark_override(self) -> None:
        """bg-indigo-100 (push notifications button) needs dark override in CSS."""
        css = read_css(CSS_PATH)
        assert ".dark .bg-indigo-100" in css, (
            "Missing .dark .bg-indigo-100 override — indigo-100 is too light on dark bg"
        )

    def test_css_has_teal_800_dark_override(self) -> None:
        """text-teal-800 (#115e59) on teal-50 dark (#0d3b3b) fails contrast — needs override."""
        css = read_css(CSS_PATH)
        assert ".dark .text-teal-800" in css, (
            "Missing .dark .text-teal-800 override — very dark on dark bg"
        )


class TestDarkModeListTemplates:
    """List and data display templates must have dark: variants."""

    def test_person_detail_sections_have_dark_bg(self) -> None:
        """Person detail page sections must have dark background."""
        html = read_template("backend/people/templates/people/person_detail.html")
        assert html.count("dark:bg-slate-800") >= 2, (
            "person_detail.html needs dark:bg-slate-800 on person header and history sections"
        )

    def test_person_detail_transaction_rows_have_dark_text(self) -> None:
        """Transaction rows in person detail need dark text variants."""
        html = read_template("backend/people/templates/people/person_detail.html")
        assert "dark:text-slate-200" in html or "dark:text-slate-300" in html, (
            "person_detail.html transaction rows missing dark text"
        )

    def test_credit_card_statement_sections_have_dark_bg(self) -> None:
        """Credit card statement sections must have dark background."""
        html = read_template(
            "backend/accounts/templates/accounts/credit_card_statement.html"
        )
        assert html.count("dark:bg-slate-800") >= 3, (
            "credit_card_statement.html needs dark:bg-slate-800 on at least 3 sections"
        )

    def test_credit_card_statement_has_dark_text(self) -> None:
        """Credit card statement headings and labels must be readable in dark mode."""
        html = read_template(
            "backend/accounts/templates/accounts/credit_card_statement.html"
        )
        assert "dark:text-slate-" in html, (
            "credit_card_statement.html missing dark text variants"
        )
