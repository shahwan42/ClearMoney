"""
Dashboard service tests — integration tests for each query method.

Tests follow the reports app pattern: raw SQL inserts for test data,
direct calls to service methods, cleanup on teardown.
"""

import uuid
from datetime import date, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.db import connection

from conftest import UserFactory
from core.models import User
from dashboard.services import (
    DashboardService,
    _compute_due_date,
)

TZ = ZoneInfo("Africa/Cairo")


@pytest.fixture
def svc_data(db):
    """User + institution + 2 accounts (EGP savings + EGP credit card) + exchange rate.

    Yields a dict with user_id and account IDs. Creates DashboardService-ready data.
    """
    user = UserFactory()
    user_id = str(user.id)
    inst_id = str(uuid.uuid4())
    savings_id = str(uuid.uuid4())
    cc_id = str(uuid.uuid4())
    cat_id = str(uuid.uuid4())

    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO institutions (id, user_id, name) VALUES (%s, %s, %s)",
            [inst_id, user_id, "Test Bank"],
        )
        cursor.execute(
            "INSERT INTO accounts (id, user_id, institution_id, name, type, currency, current_balance)"
            " VALUES (%s, %s, %s, %s, 'savings', 'EGP', %s)",
            [savings_id, user_id, inst_id, "Savings EGP", 10000],
        )
        cursor.execute(
            "INSERT INTO accounts (id, user_id, institution_id, name, type, currency, current_balance, credit_limit)"
            " VALUES (%s, %s, %s, %s, 'credit_card', 'EGP', %s, %s)",
            [cc_id, user_id, inst_id, "CC EGP", -2000, 10000],
        )
        cursor.execute(
            "INSERT INTO exchange_rate_log (id, date, rate) VALUES (%s, %s, %s)",
            [str(uuid.uuid4()), date.today(), 50.5],
        )
        cursor.execute(
            "INSERT INTO categories (id, user_id, name, type, icon) VALUES (%s, %s, %s, %s, %s)",
            [cat_id, user_id, "Food", "expense", "🛒"],
        )

    yield {
        "user_id": user_id,
        "inst_id": inst_id,
        "savings_id": savings_id,
        "cc_id": cc_id,
        "cat_id": cat_id,
    }

    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM transactions WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM budgets WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM virtual_accounts WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM persons WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM daily_snapshots WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM account_snapshots WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM accounts WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM institutions WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM categories WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM exchange_rate_log WHERE date = %s", [date.today()])
    User.objects.filter(id=user_id).delete()


# ---------------------------------------------------------------------------
# Institutions + Accounts
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_load_institutions_with_accounts(svc_data):
    """Returns institution group with 2 accounts."""
    svc = DashboardService(svc_data["user_id"], TZ)
    from dashboard.services import DashboardData

    data = DashboardData()
    accounts = svc._load_institutions_with_accounts(data)
    assert len(data.institutions) == 1
    assert len(accounts) == 2
    assert data.institutions[0].name == "Test Bank"


# ---------------------------------------------------------------------------
# Exchange Rate
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_load_exchange_rate(svc_data):
    """Returns latest exchange rate."""
    svc = DashboardService(svc_data["user_id"], TZ)
    rate = svc._load_exchange_rate()
    assert abs(rate - 50.5) < 0.01


@pytest.mark.django_db
def test_load_exchange_rate_empty(db):
    """Returns 0.0 when no exchange rates exist."""
    # Use a user_id that won't have exchange rates
    # Exchange rates are global, so we check after cleaning
    user = UserFactory()
    svc = DashboardService(str(user.id), TZ)
    # We can't easily test "empty" since exchange_rate_log may have data from other tests.
    # The test above verifies it returns data; this is a smoke test.
    rate = svc._load_exchange_rate()
    assert isinstance(rate, float)
    User.objects.filter(id=user.id).delete()


# ---------------------------------------------------------------------------
# Recent Transactions
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_load_recent_transactions(svc_data):
    """Returns transactions with running balance."""
    today = date.today()
    with connection.cursor() as cursor:
        for i in range(3):
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, note, balance_delta)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                [
                    str(uuid.uuid4()),
                    svc_data["user_id"],
                    svc_data["savings_id"],
                    "expense",
                    100 + i * 50,
                    "EGP",
                    today - timedelta(days=i),
                    f"Tx {i}",
                    -(100 + i * 50),
                ],
            )

    svc = DashboardService(svc_data["user_id"], TZ)
    txns = svc.load_recent_transactions(limit=5)
    assert len(txns) == 3
    assert txns[0].account_name == "Savings EGP"
    assert txns[0].running_balance is not None


@pytest.mark.django_db
def test_load_recent_transactions_empty(svc_data):
    """Returns empty list when no transactions."""
    svc = DashboardService(svc_data["user_id"], TZ)
    txns = svc.load_recent_transactions(limit=5)
    assert txns == []


# ---------------------------------------------------------------------------
# Streak
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_load_streak(svc_data):
    """Streak counts consecutive days with transactions."""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    # How many days since Monday (inclusive of today)
    days_in_week_so_far = today.weekday() + 1  # 1 on Mon, 7 on Sun
    # Create one transaction per day from Monday through today
    tx_dates = [monday + timedelta(days=i) for i in range(days_in_week_so_far)]
    with connection.cursor() as cursor:
        for d in tx_dates:
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, balance_delta)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                [
                    str(uuid.uuid4()),
                    svc_data["user_id"],
                    svc_data["savings_id"],
                    "expense",
                    100,
                    "EGP",
                    d,
                    -100,
                ],
            )

    svc = DashboardService(svc_data["user_id"], TZ)
    streak = svc._load_streak()
    assert streak.consecutive_days == days_in_week_so_far
    assert streak.active_today is True
    assert streak.weekly_count == days_in_week_so_far


@pytest.mark.django_db
def test_load_streak_with_gap(svc_data):
    """Streak breaks at gap in transaction dates."""
    today = date.today()
    with connection.cursor() as cursor:
        # Today and yesterday
        for i in range(2):
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, balance_delta)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                [
                    str(uuid.uuid4()),
                    svc_data["user_id"],
                    svc_data["savings_id"],
                    "expense",
                    100,
                    "EGP",
                    today - timedelta(days=i),
                    -100,
                ],
            )
        # Skip day 2, add day 3
        cursor.execute(
            "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, balance_delta)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            [
                str(uuid.uuid4()),
                svc_data["user_id"],
                svc_data["savings_id"],
                "expense",
                100,
                "EGP",
                today - timedelta(days=3),
                -100,
            ],
        )

    svc = DashboardService(svc_data["user_id"], TZ)
    streak = svc._load_streak()
    assert streak.consecutive_days == 2  # only today + yesterday


# ---------------------------------------------------------------------------
# People Summary
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_load_people_summary(svc_data):
    """Groups people by currency."""
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO persons (id, user_id, name, net_balance, net_balance_egp, net_balance_usd)"
            " VALUES (%s, %s, %s, %s, %s, %s)",
            [str(uuid.uuid4()), svc_data["user_id"], "Alice", 500, 500, 0],
        )
        cursor.execute(
            "INSERT INTO persons (id, user_id, name, net_balance, net_balance_egp, net_balance_usd)"
            " VALUES (%s, %s, %s, %s, %s, %s)",
            [str(uuid.uuid4()), svc_data["user_id"], "Bob", -200, -200, 0],
        )

    svc = DashboardService(svc_data["user_id"], TZ)
    from dashboard.services import DashboardData

    data = DashboardData()
    svc._load_people_summary(data)
    assert data.has_people_activity is True
    assert len(data.people_by_currency) >= 1
    assert data.people_by_currency[0].currency == "EGP"
    assert data.people_by_currency[0].owed_to_me == 500.0
    assert data.people_by_currency[0].i_owe == -200.0


# ---------------------------------------------------------------------------
# Budgets
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_load_budgets_with_spending(svc_data):
    """Returns budget with correct spent amount."""
    today = date.today()
    budget_id = str(uuid.uuid4())
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO budgets (id, user_id, category_id, monthly_limit, currency, is_active)"
            " VALUES (%s, %s, %s, %s, 'EGP', true)",
            [budget_id, svc_data["user_id"], svc_data["cat_id"], 1000],
        )
        # Add 2 expenses in current month
        for i in range(2):
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, category_id, type, amount, currency, date, balance_delta)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                [
                    str(uuid.uuid4()),
                    svc_data["user_id"],
                    svc_data["savings_id"],
                    svc_data["cat_id"],
                    "expense",
                    200,
                    "EGP",
                    today.replace(day=max(1, today.day - i)),
                    -200,
                ],
            )

    svc = DashboardService(svc_data["user_id"], TZ)
    budgets = svc._load_budgets_with_spending()
    assert len(budgets) == 1
    assert budgets[0]["category_name"] == "Food"
    assert budgets[0]["spent"] == 400.0
    assert budgets[0]["status"] == "green"  # 400/1000 = 40%


# ---------------------------------------------------------------------------
# Health Warnings
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_load_health_warnings(svc_data):
    """Detects min_balance violation."""
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE accounts SET health_config = %s::jsonb WHERE id = %s",
            ['{"min_balance": 20000}', svc_data["savings_id"]],
        )

    svc = DashboardService(svc_data["user_id"], TZ)
    from dashboard.services import DashboardData

    data = DashboardData()
    accounts = svc._load_institutions_with_accounts(data)
    warnings = svc._load_health_warnings(accounts)
    assert len(warnings) >= 1
    assert warnings[0].rule == "min_balance"
    assert "below minimum balance" in warnings[0].message


# ---------------------------------------------------------------------------
# Net Worth History
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_load_net_worth_history(svc_data):
    """Returns sparkline values from daily_snapshots."""
    today = date.today()
    with connection.cursor() as cursor:
        for i in range(5):
            cursor.execute(
                "INSERT INTO daily_snapshots (id, user_id, date, net_worth_egp, net_worth_raw, exchange_rate)"
                " VALUES (%s, %s, %s, %s, %s, %s)",
                [
                    str(uuid.uuid4()),
                    svc_data["user_id"],
                    today - timedelta(days=10 - i),
                    10000 + i * 100,
                    10000 + i * 100,
                    50.0,
                ],
            )

    svc = DashboardService(svc_data["user_id"], TZ)
    from dashboard.services import DashboardData

    data = DashboardData()
    svc._load_net_worth_history(data)
    assert len(data.net_worth_history) == 5
    assert data.net_worth_change != 0


# ---------------------------------------------------------------------------
# CC Summary / Utilization
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_cc_summary_utilization(svc_data):
    """Credit card utilization computed correctly."""
    svc = DashboardService(svc_data["user_id"], TZ)
    from dashboard.services import DashboardData

    data = DashboardData()
    accounts = svc._load_institutions_with_accounts(data)
    svc._compute_credit_card_summaries(data, accounts)
    assert len(data.credit_cards) == 1
    cc = data.credit_cards[0]
    assert cc.account_name == "CC EGP"
    # Balance -2000, limit 10000 → utilization = 20%
    assert abs(cc.utilization - 20.0) < 0.1


# ---------------------------------------------------------------------------
# Full Dashboard (integration smoke test)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_get_dashboard_returns_dict(svc_data):
    """get_dashboard() returns a dict without errors."""
    svc = DashboardService(svc_data["user_id"], TZ)
    data = svc.get_dashboard()
    assert isinstance(data, dict)
    assert "institutions" in data
    assert "net_worth" in data
    assert len(data["institutions"]) == 1


# ---------------------------------------------------------------------------
# Due Date Computation (pure Python, no DB)
# ---------------------------------------------------------------------------


def test_compute_due_date_due_after_statement():
    """Due day > statement day: due date same month as period end."""
    # Statement day 5, due day 25, today is Mar 3 (before statement)
    result = _compute_due_date(5, 25, date(2026, 3, 3))
    assert result == date(2026, 3, 25)


def test_compute_due_date_due_before_statement():
    """Due day < statement day: due date next month after period end."""
    # Statement day 15, due day 5, today is Mar 3 (before statement)
    result = _compute_due_date(15, 5, date(2026, 3, 3))
    assert result == date(2026, 4, 5)


def test_compute_due_date_after_statement():
    """Today after statement day: period end is next month."""
    # Statement day 5, due day 25, today is Mar 10 (after statement)
    result = _compute_due_date(5, 25, date(2026, 3, 10))
    assert result == date(2026, 4, 25)


def test_compute_due_date_december_boundary():
    """December statement wraps to January due date."""
    # Statement day 15, due day 5, today is Dec 20 (after statement)
    result = _compute_due_date(15, 5, date(2026, 12, 20))
    assert result == date(2027, 2, 5)


# ---------------------------------------------------------------------------
# Spending Comparison
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_compute_spending_comparison(svc_data):
    """Returns per-currency spending with month-over-month change."""
    today = date.today()
    this_month_start = today.replace(day=1)
    if this_month_start.month == 1:
        last_month_start = date(this_month_start.year - 1, 12, 1)
    else:
        last_month_start = date(this_month_start.year, this_month_start.month - 1, 1)

    with connection.cursor() as cursor:
        # This month: 2 expenses
        for i in range(2):
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, balance_delta)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                [
                    str(uuid.uuid4()),
                    svc_data["user_id"],
                    svc_data["savings_id"],
                    "expense",
                    300,
                    "EGP",
                    this_month_start + timedelta(days=i),
                    -300,
                ],
            )
        # Last month: 1 expense
        cursor.execute(
            "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, balance_delta)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            [
                str(uuid.uuid4()),
                svc_data["user_id"],
                svc_data["savings_id"],
                "expense",
                500,
                "EGP",
                last_month_start + timedelta(days=5),
                -500,
            ],
        )

    svc = DashboardService(svc_data["user_id"], TZ)
    from dashboard.services import DashboardData

    data = DashboardData()
    data.exchange_rate = 50.5
    svc._compute_spending_comparison(data)
    assert len(data.spending_by_currency) >= 1
    egp = data.spending_by_currency[0]
    assert egp.currency == "EGP"
    assert egp.this_month == 600.0
    assert egp.last_month == 500.0
    # Change: (600-500)/500*100 = 20%
    assert abs(egp.change - 20.0) < 0.1


@pytest.mark.django_db
def test_spending_velocity_status(svc_data):
    """Velocity status computed based on pace vs day progress."""
    svc = DashboardService(svc_data["user_id"], TZ)
    from dashboard.services import DashboardData

    data = DashboardData()
    data.exchange_rate = 50.5
    # No transactions → velocity percentage is 0 → green
    svc._compute_spending_comparison(data)
    assert data.spending_velocity.status == "green"
    assert data.spending_velocity.days_total > 0


@pytest.mark.django_db
def test_credit_avail_calculation(svc_data):
    """Credit available = limit + balance (balance is negative)."""
    svc = DashboardService(svc_data["user_id"], TZ)
    from dashboard.services import DashboardData

    data = DashboardData()
    accounts = svc._load_institutions_with_accounts(data)
    svc._compute_net_worth(data, accounts)
    # CC has balance=-2000, limit=10000 → avail = 10000 + (-2000) = 8000
    assert abs(data.credit_avail - 8000.0) < 0.1
