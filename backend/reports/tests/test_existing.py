"""
Reports app tests — reports page rendering and data aggregation.

DB tests use @pytest.mark.django_db with factory_boy fixtures for test data setup.

Chart builder tests are plain functions (no DB).
"""

from datetime import date

import pytest

from conftest import SessionFactory, UserFactory
from core.middleware import COOKIE_NAME
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
    get_spending_by_category as _get_spending_by_category,
)
from tests.factories import (
    AccountFactory,
    CategoryFactory,
    InstitutionFactory,
    TransactionFactory,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def reports_data(db):
    """User + session + institution + account + category + 4 transactions.

    Creates March 2026 data: 3 expense transactions + 1 income transaction.
    Yields a dict with user_id, session_token, account_id, category_id.
    """
    user = UserFactory()
    session = SessionFactory(user=user)

    inst = InstitutionFactory(user_id=user.id, name="Test Bank")
    acct = AccountFactory(
        user_id=user.id,
        institution_id=inst.id,
        name="Test Acct",
        type="savings",
        currency="EGP",
        current_balance=10000,
    )
    cat = CategoryFactory(user_id=user.id, name={"en": "Food"}, type="expense")

    for i in range(3):
        amount = 100 + i * 50
        TransactionFactory(
            user_id=user.id,
            account_id=acct.id,
            category_id=cat.id,
            type="expense",
            amount=amount,
            currency="EGP",
            date=date(2026, 3, 10 + i),
            note=f"Test expense {i}",
            balance_delta=-amount,
        )

    TransactionFactory(
        user_id=user.id,
        account_id=acct.id,
        type="income",
        amount=5000,
        currency="EGP",
        date=date(2026, 3, 1),
        note="Test income",
        balance_delta=5000,
    )

    yield {
        "user_id": str(user.id),
        "session_token": session.token,
        "account_id": str(acct.id),
        "category_id": str(cat.id),
    }


@pytest.fixture
def spending_data(db):
    """User + account + category + 3 expense transactions for March 2026.

    Used by SpendingByCategory and MonthSummary tests.
    Yields dict with user_id and account_id.
    """
    user = UserFactory()

    inst = InstitutionFactory(user_id=user.id, name="Test Bank")
    acct = AccountFactory(
        user_id=user.id,
        institution_id=inst.id,
        name="Test",
        type="savings",
        currency="EGP",
        current_balance=0,
    )
    cat = CategoryFactory(user_id=user.id, name={"en": "Food"}, type="expense")

    for i in range(3):
        amount = 100 + i * 50
        TransactionFactory(
            user_id=user.id,
            account_id=acct.id,
            category_id=cat.id,
            type="expense",
            amount=amount,
            currency="EGP",
            date=date(2026, 3, 10 + i),
            balance_delta=-amount,
        )

    yield {
        "user_id": str(user.id),
        "account_id": str(acct.id),
        "category_id": str(cat.id),
    }


@pytest.fixture
def summary_data(db):
    """User + account + 1 income + 3 expenses for March 2026.

    Used by MonthSummary tests.
    Yields dict with user_id.
    """
    user = UserFactory()

    inst = InstitutionFactory(user_id=user.id, name="Test Bank")
    acct = AccountFactory(
        user_id=user.id,
        institution_id=inst.id,
        name="Test",
        type="savings",
        currency="EGP",
        current_balance=0,
    )

    TransactionFactory(
        user_id=user.id,
        account_id=acct.id,
        type="income",
        amount=5000,
        currency="EGP",
        date=date(2026, 3, 1),
        balance_delta=5000,
    )

    for i in range(3):
        amount = 100 + i * 50
        TransactionFactory(
            user_id=user.id,
            account_id=acct.id,
            type="expense",
            amount=amount,
            currency="EGP",
            date=date(2026, 3, 10 + i),
            balance_delta=-amount,
        )

    yield {"user_id": str(user.id)}


# ---------------------------------------------------------------------------
# GET /reports — page rendering
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_reports_returns_200(client, reports_data):
    """Authenticated request to /reports returns 200."""
    cookie = {"HTTP_COOKIE": f"{COOKIE_NAME}={reports_data['session_token']}"}
    response = client.get("/reports", **cookie)
    assert response.status_code == 200


@pytest.mark.django_db
def test_reports_contains_chart_html(client, reports_data):
    """Reports page contains chart-related HTML."""
    cookie = {"HTTP_COOKIE": f"{COOKIE_NAME}={reports_data['session_token']}"}
    response = client.get("/reports?year=2026&month=3", **cookie)
    content = response.content.decode()
    assert "Spending by Category" in content
    assert "Income vs Expenses" in content


@pytest.mark.django_db
def test_reports_with_currency_filter(client, reports_data):
    """Reports page works with currency filter."""
    cookie = {"HTTP_COOKIE": f"{COOKIE_NAME}={reports_data['session_token']}"}
    response = client.get("/reports?year=2026&month=3&currency=EGP", **cookie)
    assert response.status_code == 200


@pytest.mark.django_db
def test_reports_month_navigation(client, reports_data):
    """Reports page contains prev/next month links."""
    cookie = {"HTTP_COOKIE": f"{COOKIE_NAME}={reports_data['session_token']}"}
    response = client.get("/reports?year=2026&month=3", **cookie)
    content = response.content.decode()
    assert "Prev" in content
    assert "Next" in content


@pytest.mark.django_db
def test_reports_empty_month(client, reports_data):
    """Reports for a month with no data returns 200."""
    cookie = {"HTTP_COOKIE": f"{COOKIE_NAME}={reports_data['session_token']}"}
    response = client.get("/reports?year=2020&month=1", **cookie)
    assert response.status_code == 200


@pytest.mark.django_db
def test_reports_redirects_without_auth(client):
    """Unauthenticated request redirects to /login."""
    response = client.get("/reports")
    assert response.status_code == 302
    assert response.url == "/login"


# ---------------------------------------------------------------------------
# _get_spending_by_category — SQL aggregation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_spending_returns_data(spending_data):
    """Should return spending with correct total for March 2026."""
    spending, total = _get_spending_by_category(spending_data["user_id"], 2026, 3)
    assert total > 0
    assert len(spending) > 0
    assert abs(total - 450.0) < 0.01


@pytest.mark.django_db
def test_spending_percentages_sum_to_100(spending_data):
    """Category percentages sum to approximately 100."""
    spending, total = _get_spending_by_category(spending_data["user_id"], 2026, 3)
    if spending:
        pct_sum = sum(s["percentage"] for s in spending)
        assert abs(pct_sum - 100.0) < 0.1


@pytest.mark.django_db
def test_spending_empty_month_returns_no_data(spending_data):
    """A month with no expenses returns an empty list."""
    spending, total = _get_spending_by_category(spending_data["user_id"], 2020, 1)
    assert spending == []
    assert total == 0.0


# ---------------------------------------------------------------------------
# _get_month_summary — income/expense totals
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_summary_returns_correct_totals(summary_data):
    """Should return correct income and expense totals."""
    summary = _get_month_summary(summary_data["user_id"], 2026, 3)
    assert summary["income"] == 5000.0
    assert abs(summary["expenses"] - 450.0) < 0.01
    assert abs(summary["net"] - 4550.0) < 0.01


# ---------------------------------------------------------------------------
# Chart builder functions — no DB
# ---------------------------------------------------------------------------


def test_build_chart_segments_empty():
    """Empty spending returns empty segments."""
    assert _build_chart_segments([], 0) == []


def test_build_chart_segments_assigns_colors():
    """Each segment gets a color from the palette (CSS custom properties for dark mode)."""
    spending = [
        {"name": "Food", "amount": 60, "percentage": 60},
        {"name": "Transport", "amount": 40, "percentage": 40},
    ]
    segments = _build_chart_segments(spending, 100)
    assert len(segments) == 2
    assert segments[0]["color"] == "var(--chart-1)"
    assert segments[1]["color"] == "var(--chart-2)"


def test_build_bar_chart_empty():
    """Empty history returns empty groups and legend."""
    groups, legend = _build_bar_chart([])
    assert groups == []
    assert legend == []


def test_build_bar_chart_normalizes_heights():
    """The tallest bar is 100%."""
    history = [
        {
            "year": 2026,
            "month": 1,
            "month_name": "January",
            "income": 1000,
            "expenses": 500,
            "net": 500,
        },
        {
            "year": 2026,
            "month": 2,
            "month_name": "February",
            "income": 2000,
            "expenses": 800,
            "net": 1200,
        },
    ]
    groups, legend = _build_bar_chart(history)
    assert len(groups) == 2
    feb_income_height = groups[1]["bars"][0]["height_pct"]
    assert abs(feb_income_height - 100.0) < 0.1
    assert len(legend) == 2
