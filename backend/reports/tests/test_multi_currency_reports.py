import pytest
from django.test import Client

from reports.services import get_monthly_report
from tests.factories import (
    AccountFactory,
    BudgetFactory,
    CategoryFactory,
    CurrencyFactory,
    InstitutionFactory,
    TransactionFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestMultiCurrencyReports:
    """Tests for multi-currency report isolation and exact-currency reporting."""

    def test_report_isolation_by_currency(self):
        import datetime as dt

        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)

        # Use a 4-year-old month so it's never in the "last 3 months" lookback
        # that the projection service uses for discretionary averaging.
        today = dt.date.today()
        old_month = dt.date(today.year - 4, today.month, 1)
        report_year, report_month = old_month.year, old_month.month

        # EGP Account
        egp_acc = AccountFactory(
            user_id=user.id,
            institution_id=inst.id,
            currency="EGP",
            current_balance=1000,
        )
        # EUR Account
        eur_acc = AccountFactory(
            user_id=user.id, institution_id=inst.id, currency="EUR", current_balance=100
        )

        category = CategoryFactory(user_id=user.id, name={"en": "Food"}, type="expense")

        # Transaction in EGP
        TransactionFactory(
            user_id=user.id,
            account_id=egp_acc.id,
            category_id=category.id,
            type="expense",
            amount=500,
            currency="EGP",
            date=old_month.replace(day=15),
        )

        # Transaction in EUR
        TransactionFactory(
            user_id=user.id,
            account_id=eur_acc.id,
            category_id=category.id,
            type="expense",
            amount=20,
            currency="EUR",
            date=old_month.replace(day=16),
        )

        # EUR Report
        report = get_monthly_report(
            str(user.id), report_year, report_month, currency="EUR"
        )

        assert report["filter_currency"] == "EUR"
        assert report["total_spending"] == 20.0
        assert len(report["spending_by_category"]) == 1
        assert report["spending_by_category"][0]["amount"] == 20.0

        # Net worth projection should only consider EUR account.
        # Current NW = 100 EUR. Report month is 4 years ago so no discretionary
        # history in the lookback window — projection stays at 100 EUR.
        assert report["projection"]["points"][0]["value"] == 100.0

    def test_pdf_export_filters_budgets_by_currency(
        self, auth_client: Client, auth_user: tuple
    ):
        user_id, _, _ = auth_user
        from unittest.mock import patch

        from auth_app.currency import set_user_active_currencies

        # Create currencies
        CurrencyFactory(code="EGP", symbol="EGP")
        CurrencyFactory(code="EUR", symbol="€")
        set_user_active_currencies(user_id, ["EGP", "EUR"])

        category = CategoryFactory(user_id=user_id, name={"en": "Food"}, type="expense")

        # EUR Budget
        BudgetFactory(
            user_id=user_id, category_id=category.id, currency="EUR", monthly_limit=100
        )
        # EGP Budget
        BudgetFactory(
            user_id=user_id, category_id=category.id, currency="EGP", monthly_limit=1000
        )

        with patch("reports.views.HTML") as mock_html:
            mock_html.return_value.write_pdf.return_value = b"%PDF-1.4 fake"
            # Request EUR PDF
            with patch("reports.views.render_to_string") as mock_render:
                mock_render.return_value = "<html>EUR report</html>"
                resp = auth_client.get(
                    "/reports/export-pdf?year=2026&month=4&currency=EUR"
                )
                assert resp.status_code == 200

                # Check that only EUR budget was passed to template
                context = mock_render.call_args[0][1]
                budgets = context["budgets"]
                assert len(budgets) == 1
                assert budgets[0].currency == "EUR"
