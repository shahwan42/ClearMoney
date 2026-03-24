"""
Reports app tests — reports page rendering and data aggregation.

DB tests use @pytest.mark.django_db with raw SQL fixtures for test data setup.

Chart builder tests are plain functions (no DB).
"""

import uuid
from datetime import date

import pytest
from django.db import connection

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

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def reports_data(db):
    """User + session + institution + account + category + 4 transactions.

    Creates March 2026 data: 3 expense transactions + 1 income transaction.
    Yields a dict with user_id, session_token, account_id, category_id.
    Cleans up on teardown.
    """
    user = UserFactory()
    session = SessionFactory(user=user)
    inst_id = str(uuid.uuid4())
    account_id = str(uuid.uuid4())
    category_id = str(uuid.uuid4())
    tx_ids = []

    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO institutions (id, user_id, name) VALUES (%s, %s, %s)",
            [inst_id, str(user.id), "Test Bank"],
        )
        cursor.execute(
            "INSERT INTO accounts (id, user_id, institution_id, name, type, currency, current_balance)"
            " VALUES (%s, %s, %s, %s, 'savings', 'EGP', %s)",
            [account_id, str(user.id), inst_id, "Test Acct", 10000],
        )
        cursor.execute(
            "INSERT INTO categories (id, user_id, name, type, icon) VALUES (%s, %s, %s, %s, %s)",
            [category_id, str(user.id), "Food", "expense", "🛒"],
        )
        for i in range(3):
            tx_id = str(uuid.uuid4())
            tx_ids.append(tx_id)
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, category_id, type, amount, currency, date, note)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                [
                    tx_id,
                    str(user.id),
                    account_id,
                    category_id,
                    "expense",
                    100 + i * 50,
                    "EGP",
                    date(2026, 3, 10 + i),
                    f"Test expense {i}",
                ],
            )
        income_id = str(uuid.uuid4())
        tx_ids.append(income_id)
        cursor.execute(
            "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, note)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            [
                income_id,
                str(user.id),
                account_id,
                "income",
                5000,
                "EGP",
                date(2026, 3, 1),
                "Test income",
            ],
        )

    yield {
        "user_id": str(user.id),
        "session_token": session.token,
        "account_id": account_id,
        "category_id": category_id,
    }

    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM transactions WHERE user_id = %s", [str(user.id)])
        cursor.execute("DELETE FROM accounts WHERE user_id = %s", [str(user.id)])
        cursor.execute("DELETE FROM institutions WHERE user_id = %s", [str(user.id)])
        cursor.execute("DELETE FROM categories WHERE user_id = %s", [str(user.id)])
    from core.models import Session, User

    Session.objects.filter(user=user).delete()
    User.objects.filter(id=user.id).delete()


@pytest.fixture
def spending_data(db):
    """User + account + category + 3 expense transactions for March 2026.

    Used by SpendingByCategory and MonthSummary tests.
    Yields dict with user_id and account_id.
    """
    user = UserFactory()
    inst_id = str(uuid.uuid4())
    account_id = str(uuid.uuid4())
    category_id = str(uuid.uuid4())

    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO institutions (id, user_id, name) VALUES (%s, %s, %s)",
            [inst_id, str(user.id), "Test Bank"],
        )
        cursor.execute(
            "INSERT INTO accounts (id, user_id, institution_id, name, type, currency, current_balance)"
            " VALUES (%s, %s, %s, %s, 'savings', 'EGP', %s)",
            [account_id, str(user.id), inst_id, "Test", 0],
        )
        cursor.execute(
            "INSERT INTO categories (id, user_id, name, type, icon) VALUES (%s, %s, %s, %s, %s)",
            [category_id, str(user.id), "Food", "expense", "🛒"],
        )
        for i in range(3):
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, category_id, type, amount, currency, date)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                [
                    str(uuid.uuid4()),
                    str(user.id),
                    account_id,
                    category_id,
                    "expense",
                    100 + i * 50,
                    "EGP",
                    date(2026, 3, 10 + i),
                ],
            )

    yield {
        "user_id": str(user.id),
        "account_id": account_id,
        "category_id": category_id,
    }

    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM transactions WHERE user_id = %s", [str(user.id)])
        cursor.execute("DELETE FROM accounts WHERE user_id = %s", [str(user.id)])
        cursor.execute("DELETE FROM institutions WHERE user_id = %s", [str(user.id)])
        cursor.execute("DELETE FROM categories WHERE user_id = %s", [str(user.id)])
    from core.models import User

    User.objects.filter(id=user.id).delete()


@pytest.fixture
def summary_data(db):
    """User + account + 1 income + 3 expenses for March 2026.

    Used by MonthSummary tests.
    Yields dict with user_id.
    """
    user = UserFactory()
    inst_id = str(uuid.uuid4())
    account_id = str(uuid.uuid4())

    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO institutions (id, user_id, name) VALUES (%s, %s, %s)",
            [inst_id, str(user.id), "Test Bank"],
        )
        cursor.execute(
            "INSERT INTO accounts (id, user_id, institution_id, name, type, currency, current_balance)"
            " VALUES (%s, %s, %s, %s, 'savings', 'EGP', %s)",
            [account_id, str(user.id), inst_id, "Test", 0],
        )
        cursor.execute(
            "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s)",
            [
                str(uuid.uuid4()),
                str(user.id),
                account_id,
                "income",
                5000,
                "EGP",
                date(2026, 3, 1),
            ],
        )
        for i in range(3):
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s)",
                [
                    str(uuid.uuid4()),
                    str(user.id),
                    account_id,
                    "expense",
                    100 + i * 50,
                    "EGP",
                    date(2026, 3, 10 + i),
                ],
            )

    yield {"user_id": str(user.id)}

    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM transactions WHERE user_id = %s", [str(user.id)])
        cursor.execute("DELETE FROM accounts WHERE user_id = %s", [str(user.id)])
        cursor.execute("DELETE FROM institutions WHERE user_id = %s", [str(user.id)])
    from core.models import User

    User.objects.filter(id=user.id).delete()


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
    """Each segment gets a color from the palette."""
    spending = [
        {"name": "Food", "amount": 60, "percentage": 60},
        {"name": "Transport", "amount": 40, "percentage": 40},
    ]
    segments = _build_chart_segments(spending, 100)
    assert len(segments) == 2
    assert segments[0]["color"] == "#0d9488"
    assert segments[1]["color"] == "#dc2626"


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
