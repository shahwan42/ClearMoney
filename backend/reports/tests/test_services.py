"""Tests for reports data functions (spending, summaries, chart builders)."""

import datetime
from decimal import Decimal
from typing import Any

import pytest

from reports.services import (
    build_bar_chart as _build_bar_chart,
)
from reports.services import (
    build_chart_segments as _build_chart_segments,
)
from reports.services import (
    get_month_summary as _get_month_summary,
)
from reports.services import (
    get_monthly_history as _get_monthly_history,
)
from reports.services import (
    get_spending_by_category as _get_spending_by_category,
)
from tests.factories import (
    AccountFactory,
    CategoryFactory,
    InstitutionFactory,
    TransactionFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestGetSpendingByCategory:
    """_get_spending_by_category() — SQL aggregation."""

    def test_no_transactions(self) -> None:
        user = UserFactory()
        spending, total = _get_spending_by_category(str(user.id), 2026, 3)
        assert spending == []
        assert total == 0.0

    def test_single_category(self) -> None:
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        account = AccountFactory(
            user_id=user.id, institution_id=inst.id, currency="EGP"
        )
        category = CategoryFactory(user_id=user.id, type="expense")
        TransactionFactory(
            user_id=user.id,
            account_id=account.id,
            category_id=category.id,
            type="expense",
            amount=Decimal("500"),
            currency="EGP",
            date=datetime.date(2026, 3, 15),
        )
        spending, total = _get_spending_by_category(str(user.id), 2026, 3)
        assert len(spending) == 1
        assert total == 500.0
        assert spending[0]["name"] == category.name

    def test_multiple_categories(self) -> None:
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        account = AccountFactory(
            user_id=user.id, institution_id=inst.id, currency="EGP"
        )
        cat1 = CategoryFactory(user_id=user.id, name="Food", type="expense")
        cat2 = CategoryFactory(user_id=user.id, name="Transport", type="expense")
        TransactionFactory(
            user_id=user.id,
            account_id=account.id,
            category_id=cat1.id,
            type="expense",
            amount=Decimal("300"),
            currency="EGP",
            date=datetime.date(2026, 3, 10),
        )
        TransactionFactory(
            user_id=user.id,
            account_id=account.id,
            category_id=cat2.id,
            type="expense",
            amount=Decimal("200"),
            currency="EGP",
            date=datetime.date(2026, 3, 12),
        )
        spending, total = _get_spending_by_category(str(user.id), 2026, 3)
        assert len(spending) == 2
        assert total == 500.0

    def test_income_excluded(self) -> None:
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        account = AccountFactory(
            user_id=user.id, institution_id=inst.id, currency="EGP"
        )
        cat = CategoryFactory(user_id=user.id, type="income")
        TransactionFactory(
            user_id=user.id,
            account_id=account.id,
            category_id=cat.id,
            type="income",
            amount=Decimal("5000"),
            currency="EGP",
            date=datetime.date(2026, 3, 1),
        )
        spending, total = _get_spending_by_category(str(user.id), 2026, 3)
        assert total == 0.0

    def test_filter_by_currency(self) -> None:
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        egp_acc = AccountFactory(
            user_id=user.id, institution_id=inst.id, currency="EGP"
        )
        usd_acc = AccountFactory(
            user_id=user.id, institution_id=inst.id, currency="USD"
        )
        cat = CategoryFactory(user_id=user.id, type="expense")
        TransactionFactory(
            user_id=user.id,
            account_id=egp_acc.id,
            category_id=cat.id,
            type="expense",
            amount=Decimal("1000"),
            currency="EGP",
            date=datetime.date(2026, 3, 5),
        )
        TransactionFactory(
            user_id=user.id,
            account_id=usd_acc.id,
            category_id=cat.id,
            type="expense",
            amount=Decimal("50"),
            currency="USD",
            date=datetime.date(2026, 3, 5),
        )
        spending, total = _get_spending_by_category(
            str(user.id), 2026, 3, currency="EGP"
        )
        assert total == 1000.0

    def test_filter_by_account(self) -> None:
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        acc1 = AccountFactory(user_id=user.id, institution_id=inst.id, currency="EGP")
        acc2 = AccountFactory(user_id=user.id, institution_id=inst.id, currency="EGP")
        cat = CategoryFactory(user_id=user.id, type="expense")
        TransactionFactory(
            user_id=user.id,
            account_id=acc1.id,
            category_id=cat.id,
            type="expense",
            amount=Decimal("300"),
            currency="EGP",
            date=datetime.date(2026, 3, 5),
        )
        TransactionFactory(
            user_id=user.id,
            account_id=acc2.id,
            category_id=cat.id,
            type="expense",
            amount=Decimal("200"),
            currency="EGP",
            date=datetime.date(2026, 3, 5),
        )
        spending, total = _get_spending_by_category(
            str(user.id), 2026, 3, account_id=str(acc1.id)
        )
        assert total == 300.0


@pytest.mark.django_db
class TestGetMonthSummary:
    """_get_month_summary() — income and expense totals."""

    def test_no_transactions(self) -> None:
        user = UserFactory()
        result = _get_month_summary(str(user.id), 2026, 3)
        assert result["income"] == 0
        assert result["expenses"] == 0
        assert result["net"] == 0

    def test_income_and_expenses(self) -> None:
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        account = AccountFactory(
            user_id=user.id, institution_id=inst.id, currency="EGP"
        )
        exp_cat = CategoryFactory(user_id=user.id, type="expense")
        inc_cat = CategoryFactory(user_id=user.id, type="income")
        TransactionFactory(
            user_id=user.id,
            account_id=account.id,
            category_id=exp_cat.id,
            type="expense",
            amount=Decimal("500"),
            currency="EGP",
            date=datetime.date(2026, 3, 10),
        )
        TransactionFactory(
            user_id=user.id,
            account_id=account.id,
            category_id=inc_cat.id,
            type="income",
            amount=Decimal("3000"),
            currency="EGP",
            date=datetime.date(2026, 3, 1),
        )
        result = _get_month_summary(str(user.id), 2026, 3)
        assert float(result["income"]) == 3000.0
        assert float(result["expenses"]) == 500.0
        assert float(result["net"]) == 2500.0


@pytest.mark.django_db
class TestGetMonthlyHistory:
    """_get_monthly_history() — 6-month lookback."""

    def test_returns_six_months(self) -> None:
        user = UserFactory()
        history = _get_monthly_history(str(user.id), 2026, 3)
        assert len(history) == 6

    def test_year_boundary(self) -> None:
        user = UserFactory()
        history = _get_monthly_history(str(user.id), 2026, 2)
        months = [(h["year"], h["month"]) for h in history]
        assert (2025, 9) in months


class TestBuildChartSegments:
    """_build_chart_segments() — pure function, no DB."""

    def test_empty_spending(self) -> None:
        segments = _build_chart_segments([], 0.0)
        assert segments == []

    def test_single_category(self) -> None:
        spending: list[dict[str, Any]] = [
            {"name": "Food", "icon": "x", "amount": 500.0, "percentage": 100.0}
        ]
        segments = _build_chart_segments(spending, 500.0)
        assert len(segments) == 1
        assert segments[0]["percentage"] == 100.0
        assert segments[0]["color"] == "#0d9488"

    def test_multiple_categories_colors(self) -> None:
        spending: list[dict[str, Any]] = [
            {"name": "Food", "icon": "x", "amount": 300.0, "percentage": 60.0},
            {"name": "Transport", "icon": "x", "amount": 200.0, "percentage": 40.0},
        ]
        segments = _build_chart_segments(spending, 500.0)
        assert len(segments) == 2
        assert segments[0]["color"] != segments[1]["color"]


class TestBuildBarChart:
    """_build_bar_chart() — pure function, no DB."""

    def test_empty_history(self) -> None:
        groups, legend = _build_bar_chart([])
        assert groups == []
        assert legend == []

    def test_basic_history(self) -> None:
        history: list[dict[str, Any]] = [
            {
                "year": 2026,
                "month": 1,
                "month_name": "January",
                "income": 5000,
                "expenses": 3000,
                "net": 2000,
            },
            {
                "year": 2026,
                "month": 2,
                "month_name": "February",
                "income": 5000,
                "expenses": 4000,
                "net": 1000,
            },
        ]
        groups, legend = _build_bar_chart(history)
        assert len(groups) == 2
        assert len(legend) == 2

    def test_height_normalization(self) -> None:
        history: list[dict[str, Any]] = [
            {
                "year": 2026,
                "month": 1,
                "month_name": "January",
                "income": 10000,
                "expenses": 5000,
                "net": 5000,
            },
            {
                "year": 2026,
                "month": 2,
                "month_name": "February",
                "income": 2000,
                "expenses": 1000,
                "net": 1000,
            },
        ]
        groups, _ = _build_bar_chart(history)
        max_height = max(bar["height_pct"] for group in groups for bar in group["bars"])
        assert max_height == 100.0
