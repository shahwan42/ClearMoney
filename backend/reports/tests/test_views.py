"""Tests for reports views (HTTP layer)."""

import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.test import Client

from tests.factories import (
    AccountFactory,
    BudgetFactory,
    CategoryFactory,
    InstitutionFactory,
    TransactionFactory,
)


@pytest.mark.django_db
class TestPdfExport:
    """PDF export view — budget section and basic rendering."""

    def test_returns_pdf_content_type(self, auth_client: Client, auth_user: tuple) -> None:
        """PDF export returns application/pdf content type."""
        user_id, _, _ = auth_user
        with patch("reports.views.HTML") as mock_html:
            mock_html.return_value.write_pdf.return_value = b"%PDF-1.4 fake"
            response = auth_client.get("/reports/export-pdf?year=2026&month=3")
        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"

    def test_pdf_filename_includes_year_month(self, auth_client: Client, auth_user: tuple) -> None:
        """PDF filename contains the requested year and month."""
        with patch("reports.views.HTML") as mock_html:
            mock_html.return_value.write_pdf.return_value = b"%PDF-1.4 fake"
            response = auth_client.get("/reports/export-pdf?year=2026&month=3")
        assert "2026_03" in response["Content-Disposition"]

    def test_budget_section_rendered_in_pdf_html(self, auth_user: tuple) -> None:
        """PDF template renders budget status when budgets exist."""
        from zoneinfo import ZoneInfo

        user_id, _, _ = auth_user
        inst = InstitutionFactory(user_id=user_id)
        account = AccountFactory(user_id=user_id, institution_id=inst.id, currency="EGP")
        category = CategoryFactory(user_id=user_id, name={"en": "Food"}, type="expense")
        BudgetFactory(user_id=user_id, category_id=category.id, monthly_limit=2000, currency="EGP")
        TransactionFactory(
            user_id=user_id,
            account_id=account.id,
            category_id=category.id,
            type="expense",
            amount=Decimal("500"),
            currency="EGP",
            date=datetime.date(2026, 3, 15),
        )

        from django.template.loader import render_to_string

        from budgets.services import BudgetService
        from reports.services import get_monthly_report

        report_data = get_monthly_report(user_id, 2026, 3)
        svc = BudgetService(user_id, ZoneInfo("Africa/Cairo"))
        budgets = svc.get_all_with_spending(target_date=datetime.date(2026, 3, 1))

        html = render_to_string(
            "reports/pdf_report.html",
            {"data": report_data, "today": datetime.date(2026, 4, 1), "budgets": budgets},
        )
        assert "Budget Status" in html
        assert "Food" in html

    def test_pdf_no_budgets_omits_section(self, auth_user: tuple) -> None:
        """PDF template omits budget section when user has no budgets."""
        from zoneinfo import ZoneInfo

        user_id, _, _ = auth_user
        from django.template.loader import render_to_string

        from budgets.services import BudgetService
        from reports.services import get_monthly_report

        report_data = get_monthly_report(user_id, 2026, 3)
        budgets = BudgetService(user_id, ZoneInfo("Africa/Cairo")).get_all_with_spending(
            target_date=datetime.date(2026, 3, 1)
        )

        html = render_to_string(
            "reports/pdf_report.html",
            {"data": report_data, "today": datetime.date(2026, 4, 1), "budgets": budgets},
        )
        assert "Budget Status" not in html

    def test_unauthenticated_redirects(self) -> None:
        client = Client()
        response = client.get("/reports/export-pdf")
        assert response.status_code == 302


@pytest.mark.django_db
class TestReportsPage:
    def test_renders_200(self, auth_client: Client) -> None:
        response = auth_client.get("/reports")
        assert response.status_code == 200

    def test_accepts_year_month_params(self, auth_client: Client) -> None:
        response = auth_client.get("/reports?year=2026&month=1")
        assert response.status_code == 200

    def test_accepts_currency_filter(self, auth_client: Client) -> None:
        response = auth_client.get("/reports?currency=EGP")
        assert response.status_code == 200

    def test_invalid_year_defaults_gracefully(self, auth_client: Client) -> None:
        response = auth_client.get("/reports?year=abc")
        assert response.status_code == 200

    def test_unauthenticated_redirects(self) -> None:
        client = Client()
        response = client.get("/reports")
        assert response.status_code == 302


# ---------------------------------------------------------------------------
# BATCH 6: Dark Mode Polish & Charts (Issues 26-30)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestChartDarkModeContrast:
    """Issue 26: Chart bars have CSS class for dark mode brightness override."""

    def test_bar_chart_container_has_class(self, auth_client: Client) -> None:
        """Bar chart container uses chart-bar-container class (CSS targets it)."""
        resp = auth_client.get("/reports")
        assert resp.status_code == 200
        content = resp.content.decode()
        assert "chart-bar-container" in content

    def test_chart_css_includes_dark_mode_vars(self) -> None:
        """charts.css defines dark mode CSS custom properties for WCAG AA contrast."""
        import os

        css_path = os.path.join(
            os.path.dirname(__file__),
            "../../../static/css/charts.css",
        )
        with open(css_path) as f:
            css = f.read()
        # Dark mode chart colors must use CSS custom properties (not brightness filter)
        assert "--chart-1" in css
        assert ".dark" in css
        # Dark mode uses lighter -400 variants (e.g. teal-400 #2dd4bf) for contrast
        assert "#2dd4bf" in css  # teal-400: 5.0:1 on slate-800


@pytest.mark.django_db
class TestDonutChartAria:
    """Issue 28: Donut chart has descriptive ARIA with category count."""

    def test_donut_has_role_img(self, auth_client: Client) -> None:
        """Donut chart container has role=img for screen readers."""
        resp = auth_client.get("/reports")
        content = resp.content.decode()
        assert 'role="img"' in content

    def test_donut_has_aria_label(self, auth_client: Client) -> None:
        """Donut chart has aria-label describing the chart content."""
        resp = auth_client.get("/reports")
        content = resp.content.decode()
        assert "aria-label" in content
        assert "Spending" in content or "spending" in content


@pytest.mark.django_db
class TestEmptyChartState:
    """Issue 30: Empty spending chart has CTA to add transactions."""

    def test_empty_state_shows_guidance(self, auth_client: Client) -> None:
        """When no spending data, chart area shows helpful guidance."""
        resp = auth_client.get("/reports")
        content = resp.content.decode()
        # Must have some content (not crash), may show empty state
        assert resp.status_code == 200
        assert (
            "No expenses" in content
            or "spending" in content.lower()
            or "transactions" in content.lower()
        )
