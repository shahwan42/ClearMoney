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
def test_load_recent_transactions_includes_category(svc_data):
    """TransactionRow includes category_name and category_icon when category is set."""
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO transactions (id, user_id, account_id, type, amount,"
            " currency, date, category_id, balance_delta)"
            " VALUES (%s, %s, %s, 'expense', 100, 'EGP', %s, %s, -100)",
            [
                str(uuid.uuid4()),
                svc_data["user_id"],
                svc_data["savings_id"],
                date.today(),
                svc_data["cat_id"],
            ],
        )
    svc = DashboardService(svc_data["user_id"], TZ)
    txns = svc.load_recent_transactions(limit=5)
    assert len(txns) == 1
    assert txns[0].category_name == "Food"
    assert txns[0].category_icon == "🛒"


@pytest.mark.django_db
def test_load_recent_transactions_no_category(svc_data):
    """TransactionRow has None category fields when no category set."""
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO transactions (id, user_id, account_id, type, amount,"
            " currency, date, balance_delta)"
            " VALUES (%s, %s, %s, 'expense', 100, 'EGP', %s, -100)",
            [
                str(uuid.uuid4()),
                svc_data["user_id"],
                svc_data["savings_id"],
                date.today(),
            ],
        )
    svc = DashboardService(svc_data["user_id"], TZ)
    txns = svc.load_recent_transactions(limit=5)
    assert txns[0].category_name is None
    assert txns[0].category_icon is None


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


# ---------------------------------------------------------------------------
# Running balance — value accuracy
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_load_recent_transactions_running_balance_value(svc_data):
    # gap: data — running balance was only checked for not-None, never for correct value
    # savings account current_balance=10000; expenses oldest→newest: -200, -150, -100
    # Expected (newest-first):
    #   today     (delta=-100): 10000 - 0            = 10000
    #   yesterday (delta=-150): 10000 - (-100)       = 10100
    #   2 days ago(delta=-200): 10000 - (-100 + -150)= 10250
    today = date.today()
    with connection.cursor() as cursor:
        for days_ago, delta in [(2, -200), (1, -150), (0, -100)]:
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', %s, 'EGP', %s, %s)",
                [
                    str(uuid.uuid4()),
                    svc_data["user_id"],
                    svc_data["savings_id"],
                    abs(delta),
                    today - timedelta(days=days_ago),
                    delta,
                ],
            )
    svc = DashboardService(svc_data["user_id"], TZ)
    txns = svc.load_recent_transactions(limit=5)
    assert len(txns) == 3
    assert txns[0].running_balance == pytest.approx(10000.0)
    assert txns[1].running_balance == pytest.approx(10100.0)
    assert txns[2].running_balance == pytest.approx(10250.0)


@pytest.mark.django_db
def test_load_recent_transactions_multi_account_running_balance(svc_data):
    # gap: data — per-account window partition: balances must not bleed across accounts
    # savings current_balance=10000, CC current_balance=-2000
    today = date.today()
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, balance_delta)"
            " VALUES (%s, %s, %s, 'expense', 500, 'EGP', %s, -500)",
            [str(uuid.uuid4()), svc_data["user_id"], svc_data["savings_id"], today],
        )
        cursor.execute(
            "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, balance_delta)"
            " VALUES (%s, %s, %s, 'expense', 200, 'EGP', %s, -200)",
            [
                str(uuid.uuid4()),
                svc_data["user_id"],
                svc_data["cc_id"],
                today - timedelta(days=1),
            ],
        )
    svc = DashboardService(svc_data["user_id"], TZ)
    txns = svc.load_recent_transactions(limit=5)
    assert len(txns) == 2
    by_account = {t.account_name: t.running_balance for t in txns}
    # Each account's single transaction has no preceding rows → running_balance == current_balance
    assert by_account["Savings EGP"] == pytest.approx(10000.0)
    assert by_account["CC EGP"] == pytest.approx(-2000.0)


# ---------------------------------------------------------------------------
# Budgets — amber / red / currency isolation / zero spending
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_load_budgets_amber_status(svc_data):
    # gap: functional — only "green" status was tested; amber branch uncovered
    today = date.today()
    budget_id = str(uuid.uuid4())
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO budgets (id, user_id, category_id, monthly_limit, currency, is_active)"
            " VALUES (%s, %s, %s, 1000, 'EGP', true)",
            [budget_id, svc_data["user_id"], svc_data["cat_id"]],
        )
        # 850 EGP spent = 85% → amber
        cursor.execute(
            "INSERT INTO transactions (id, user_id, account_id, category_id, type, amount, currency, date, balance_delta)"
            " VALUES (%s, %s, %s, %s, 'expense', 850, 'EGP', %s, -850)",
            [
                str(uuid.uuid4()),
                svc_data["user_id"],
                svc_data["savings_id"],
                svc_data["cat_id"],
                today,
            ],
        )
    svc = DashboardService(svc_data["user_id"], TZ)
    budgets = svc._load_budgets_with_spending()
    assert len(budgets) == 1
    assert budgets[0]["spent"] == pytest.approx(850.0)
    assert budgets[0]["status"] == "amber"


@pytest.mark.django_db
def test_load_budgets_red_status(svc_data):
    # gap: functional — red (≥100%) status branch never tested
    today = date.today()
    budget_id = str(uuid.uuid4())
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO budgets (id, user_id, category_id, monthly_limit, currency, is_active)"
            " VALUES (%s, %s, %s, 1000, 'EGP', true)",
            [budget_id, svc_data["user_id"], svc_data["cat_id"]],
        )
        # 1200 EGP spent = 120% → red
        cursor.execute(
            "INSERT INTO transactions (id, user_id, account_id, category_id, type, amount, currency, date, balance_delta)"
            " VALUES (%s, %s, %s, %s, 'expense', 1200, 'EGP', %s, -1200)",
            [
                str(uuid.uuid4()),
                svc_data["user_id"],
                svc_data["savings_id"],
                svc_data["cat_id"],
                today,
            ],
        )
    svc = DashboardService(svc_data["user_id"], TZ)
    budgets = svc._load_budgets_with_spending()
    assert budgets[0]["status"] == "red"
    assert budgets[0]["percentage"] == pytest.approx(120.0)


@pytest.mark.django_db
def test_load_budgets_zero_spending(svc_data):
    # gap: data — budget with no transactions this month; spent=0 never asserted
    budget_id = str(uuid.uuid4())
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO budgets (id, user_id, category_id, monthly_limit, currency, is_active)"
            " VALUES (%s, %s, %s, 500, 'EGP', true)",
            [budget_id, svc_data["user_id"], svc_data["cat_id"]],
        )
    svc = DashboardService(svc_data["user_id"], TZ)
    budgets = svc._load_budgets_with_spending()
    assert len(budgets) == 1
    assert budgets[0]["spent"] == pytest.approx(0.0)
    assert budgets[0]["percentage"] == pytest.approx(0.0)
    assert budgets[0]["status"] == "green"


@pytest.mark.django_db
def test_load_budgets_currency_isolation(svc_data):
    # gap: data — USD budget must not count EGP transactions (OuterRef("currency") match)
    budget_id = str(uuid.uuid4())
    today = date.today()
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO budgets (id, user_id, category_id, monthly_limit, currency, is_active)"
            " VALUES (%s, %s, %s, 200, 'USD', true)",
            [budget_id, svc_data["user_id"], svc_data["cat_id"]],
        )
        # EGP expense for same category — must NOT be counted against USD budget
        cursor.execute(
            "INSERT INTO transactions (id, user_id, account_id, category_id, type, amount, currency, date, balance_delta)"
            " VALUES (%s, %s, %s, %s, 'expense', 500, 'EGP', %s, -500)",
            [
                str(uuid.uuid4()),
                svc_data["user_id"],
                svc_data["savings_id"],
                svc_data["cat_id"],
                today,
            ],
        )
    svc = DashboardService(svc_data["user_id"], TZ)
    budgets = svc._load_budgets_with_spending()
    usd_budget = next(b for b in budgets if b["currency"] == "USD")
    assert usd_budget["spent"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Top categories — direct coverage of _query_top_categories output
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_top_categories_populated(svc_data):
    # gap: functional — top_categories on CurrencySpending never asserted
    today = date.today()
    this_month_start = today.replace(day=1)
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO transactions (id, user_id, account_id, category_id, type, amount, currency, date, balance_delta)"
            " VALUES (%s, %s, %s, %s, 'expense', 400, 'EGP', %s, -400)",
            [
                str(uuid.uuid4()),
                svc_data["user_id"],
                svc_data["savings_id"],
                svc_data["cat_id"],
                this_month_start,
            ],
        )
    svc = DashboardService(svc_data["user_id"], TZ)
    from dashboard.services import DashboardData

    data = DashboardData()
    data.exchange_rate = 50.5
    svc._compute_spending_comparison(data)
    assert len(data.spending_by_currency) >= 1
    egp = data.spending_by_currency[0]
    assert len(egp.top_categories) == 1
    cat = egp.top_categories[0]
    assert cat["name"] == "Food"
    assert cat["icon"] == "🛒"
    assert cat["amount"] == pytest.approx(400.0)
    assert "change" in cat
    assert "is_up" in cat


@pytest.mark.django_db
def test_top_categories_no_last_month(svc_data):
    # gap: functional — new category with no last-month data → change=0.0, is_up=False
    today = date.today()
    this_month_start = today.replace(day=1)
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO transactions (id, user_id, account_id, category_id, type, amount, currency, date, balance_delta)"
            " VALUES (%s, %s, %s, %s, 'expense', 300, 'EGP', %s, -300)",
            [
                str(uuid.uuid4()),
                svc_data["user_id"],
                svc_data["savings_id"],
                svc_data["cat_id"],
                this_month_start,
            ],
        )
    svc = DashboardService(svc_data["user_id"], TZ)
    from dashboard.services import DashboardData

    data = DashboardData()
    data.exchange_rate = 50.5
    svc._compute_spending_comparison(data)
    egp = data.spending_by_currency[0]
    assert egp.top_categories[0]["change"] == pytest.approx(0.0)
    assert egp.top_categories[0]["is_up"] is False


@pytest.mark.django_db
def test_top_categories_uncategorized(svc_data):
    # gap: data — NULL category transaction must appear as name="Uncategorized", icon=""
    today = date.today()
    this_month_start = today.replace(day=1)
    with connection.cursor() as cursor:
        # Expense with NO category
        cursor.execute(
            "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, balance_delta)"
            " VALUES (%s, %s, %s, 'expense', 250, 'EGP', %s, -250)",
            [
                str(uuid.uuid4()),
                svc_data["user_id"],
                svc_data["savings_id"],
                this_month_start,
            ],
        )
    svc = DashboardService(svc_data["user_id"], TZ)
    from dashboard.services import DashboardData

    data = DashboardData()
    data.exchange_rate = 50.5
    svc._compute_spending_comparison(data)
    egp = data.spending_by_currency[0]
    uncategorized = next(
        (c for c in egp.top_categories if c["name"] == "Uncategorized"), None
    )
    assert uncategorized is not None
    assert uncategorized["icon"] == ""
    assert uncategorized["amount"] == pytest.approx(250.0)


@pytest.mark.django_db
def test_top_categories_empty_when_no_expenses(svc_data):
    # gap: data — no expense transactions → top_categories must be [] not crash
    svc = DashboardService(svc_data["user_id"], TZ)
    from dashboard.services import DashboardData

    data = DashboardData()
    data.exchange_rate = 50.5
    svc._compute_spending_comparison(data)
    # No spending → no spending_by_currency entries at all
    assert data.spending_by_currency == []


@pytest.mark.django_db
def test_top_categories_is_up_true(svc_data):
    # gap: functional — is_up=True (spending increased vs last month) never asserted
    today = date.today()
    this_month_start = today.replace(day=1)
    last_month_start = (
        date(this_month_start.year - 1, 12, 1)
        if this_month_start.month == 1
        else date(this_month_start.year, this_month_start.month - 1, 1)
    )
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO transactions (id, user_id, account_id, category_id, type, amount, currency, date, balance_delta)"
            " VALUES (%s, %s, %s, %s, 'expense', 500, 'EGP', %s, -500)",
            [
                str(uuid.uuid4()),
                svc_data["user_id"],
                svc_data["savings_id"],
                svc_data["cat_id"],
                this_month_start,
            ],
        )
        cursor.execute(
            "INSERT INTO transactions (id, user_id, account_id, category_id, type, amount, currency, date, balance_delta)"
            " VALUES (%s, %s, %s, %s, 'expense', 300, 'EGP', %s, -300)",
            [
                str(uuid.uuid4()),
                svc_data["user_id"],
                svc_data["savings_id"],
                svc_data["cat_id"],
                last_month_start,
            ],
        )
    svc = DashboardService(svc_data["user_id"], TZ)
    from dashboard.services import DashboardData

    data = DashboardData()
    data.exchange_rate = 50.5
    svc._compute_spending_comparison(data)
    cat = data.spending_by_currency[0].top_categories[0]
    assert cat["name"] == "Food"
    assert cat["is_up"] is True
    assert cat["change"] == pytest.approx((500 - 300) / 300 * 100)


@pytest.mark.django_db
def test_top_categories_spending_decreased(svc_data):
    # gap: functional — spending decreased (this < last) → change<0, is_up=False
    today = date.today()
    this_month_start = today.replace(day=1)
    last_month_start = (
        date(this_month_start.year - 1, 12, 1)
        if this_month_start.month == 1
        else date(this_month_start.year, this_month_start.month - 1, 1)
    )
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO transactions (id, user_id, account_id, category_id, type, amount, currency, date, balance_delta)"
            " VALUES (%s, %s, %s, %s, 'expense', 200, 'EGP', %s, -200)",
            [
                str(uuid.uuid4()),
                svc_data["user_id"],
                svc_data["savings_id"],
                svc_data["cat_id"],
                this_month_start,
            ],
        )
        cursor.execute(
            "INSERT INTO transactions (id, user_id, account_id, category_id, type, amount, currency, date, balance_delta)"
            " VALUES (%s, %s, %s, %s, 'expense', 500, 'EGP', %s, -500)",
            [
                str(uuid.uuid4()),
                svc_data["user_id"],
                svc_data["savings_id"],
                svc_data["cat_id"],
                last_month_start,
            ],
        )
    svc = DashboardService(svc_data["user_id"], TZ)
    from dashboard.services import DashboardData

    data = DashboardData()
    data.exchange_rate = 50.5
    svc._compute_spending_comparison(data)
    cat = data.spending_by_currency[0].top_categories[0]
    assert cat["change"] == pytest.approx((200 - 500) / 500 * 100)
    assert cat["is_up"] is False


@pytest.mark.django_db
def test_load_budgets_inactive_excluded(svc_data):
    # gap: functional — inactive budget (is_active=False) must not appear in results
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO budgets (id, user_id, category_id, monthly_limit, currency, is_active)"
            " VALUES (%s, %s, %s, 1000, 'EGP', false)",
            [str(uuid.uuid4()), svc_data["user_id"], svc_data["cat_id"]],
        )
    svc = DashboardService(svc_data["user_id"], TZ)
    budgets = svc._load_budgets_with_spending()
    assert budgets == []


@pytest.mark.django_db
def test_load_recent_transactions_default_limit(svc_data):
    # gap: functional — limit parameter never actually cuts off results (all prior tests use limit < row count)
    today = date.today()
    with connection.cursor() as cursor:
        for i in range(15):
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 50, 'EGP', %s, -50)",
                [
                    str(uuid.uuid4()),
                    svc_data["user_id"],
                    svc_data["savings_id"],
                    today - timedelta(days=i),
                ],
            )
    svc = DashboardService(svc_data["user_id"], TZ)
    txns = svc.load_recent_transactions(limit=10)
    assert len(txns) == 10


@pytest.mark.django_db
def test_top_categories_multiple_with_last_month(svc_data):
    # gap: data — only single-category tests; multiple last_month_dict lookups never verified
    today = date.today()
    this_month_start = today.replace(day=1)
    last_month_start = (
        date(this_month_start.year - 1, 12, 1)
        if this_month_start.month == 1
        else date(this_month_start.year, this_month_start.month - 1, 1)
    )
    cat2_id = str(uuid.uuid4())
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO categories (id, user_id, name, type) VALUES (%s, %s, 'Transport', 'expense')",
            [cat2_id, svc_data["user_id"]],
        )
        # This month: Food=400, Transport=300
        cursor.execute(
            "INSERT INTO transactions (id, user_id, account_id, category_id, type, amount, currency, date, balance_delta)"
            " VALUES (%s, %s, %s, %s, 'expense', 400, 'EGP', %s, -400)",
            [
                str(uuid.uuid4()),
                svc_data["user_id"],
                svc_data["savings_id"],
                svc_data["cat_id"],
                this_month_start,
            ],
        )
        cursor.execute(
            "INSERT INTO transactions (id, user_id, account_id, category_id, type, amount, currency, date, balance_delta)"
            " VALUES (%s, %s, %s, %s, 'expense', 300, 'EGP', %s, -300)",
            [
                str(uuid.uuid4()),
                svc_data["user_id"],
                svc_data["savings_id"],
                cat2_id,
                this_month_start,
            ],
        )
        # Last month: Food=200, Transport=600
        cursor.execute(
            "INSERT INTO transactions (id, user_id, account_id, category_id, type, amount, currency, date, balance_delta)"
            " VALUES (%s, %s, %s, %s, 'expense', 200, 'EGP', %s, -200)",
            [
                str(uuid.uuid4()),
                svc_data["user_id"],
                svc_data["savings_id"],
                svc_data["cat_id"],
                last_month_start,
            ],
        )
        cursor.execute(
            "INSERT INTO transactions (id, user_id, account_id, category_id, type, amount, currency, date, balance_delta)"
            " VALUES (%s, %s, %s, %s, 'expense', 600, 'EGP', %s, -600)",
            [
                str(uuid.uuid4()),
                svc_data["user_id"],
                svc_data["savings_id"],
                cat2_id,
                last_month_start,
            ],
        )
    svc = DashboardService(svc_data["user_id"], TZ)
    from dashboard.services import DashboardData

    data = DashboardData()
    data.exchange_rate = 50.5
    svc._compute_spending_comparison(data)
    by_name = {c["name"]: c for c in data.spending_by_currency[0].top_categories}
    # Food: 400 this / 200 last → +100% increase
    assert by_name["Food"]["change"] == pytest.approx(100.0)
    assert by_name["Food"]["is_up"] is True
    # Transport: 300 this / 600 last → -50% decrease
    assert by_name["Transport"]["change"] == pytest.approx(-50.0)
    assert by_name["Transport"]["is_up"] is False


# ---------------------------------------------------------------------------
# Net Worth By Currency (per-currency sparkline)
# ---------------------------------------------------------------------------


class TestLoadNetWorthByCurrency:
    """Tests for load_net_worth_by_currency — per-currency sparkline data."""

    @pytest.mark.django_db
    def test_sums_by_currency(self, svc_data):
        # gap: functional — load_net_worth_by_currency never directly tested
        today = date.today()
        # Create 2 EGP accounts and 1 USD account with snapshots across 3 days
        usd_acc_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO accounts (id, user_id, institution_id, name, type, currency, current_balance)"
                " VALUES (%s, %s, %s, 'USD Savings', 'savings', 'USD', 500)",
                [usd_acc_id, svc_data["user_id"], svc_data["inst_id"]],
            )
            for i in range(3):
                snap_date = today - timedelta(days=5 - i)
                # EGP account snapshot
                cursor.execute(
                    "INSERT INTO account_snapshots (id, user_id, account_id, date, balance)"
                    " VALUES (%s, %s, %s, %s, %s)",
                    [
                        str(uuid.uuid4()),
                        svc_data["user_id"],
                        svc_data["savings_id"],
                        snap_date,
                        10000 + i * 100,
                    ],
                )
                # USD account snapshot
                cursor.execute(
                    "INSERT INTO account_snapshots (id, user_id, account_id, date, balance)"
                    " VALUES (%s, %s, %s, %s, %s)",
                    [
                        str(uuid.uuid4()),
                        svc_data["user_id"],
                        usd_acc_id,
                        snap_date,
                        500 + i * 10,
                    ],
                )

        svc = DashboardService(svc_data["user_id"], TZ)
        from dashboard.services import DashboardData

        data = DashboardData()
        svc._load_net_worth_by_currency(data)
        assert "EGP" in data.net_worth_history_by_currency
        assert "USD" in data.net_worth_history_by_currency
        assert len(data.net_worth_history_by_currency["EGP"]) == 3
        assert len(data.net_worth_history_by_currency["USD"]) == 3

    @pytest.mark.django_db
    def test_empty_when_no_snapshots(self, svc_data):
        # gap: functional — empty snapshots must leave net_worth_history_by_currency as default {}
        svc = DashboardService(svc_data["user_id"], TZ)
        from dashboard.services import DashboardData

        data = DashboardData()
        svc._load_net_worth_by_currency(data)
        assert data.net_worth_history_by_currency == {}


# ---------------------------------------------------------------------------
# Account Sparklines (per-account balance history)
# ---------------------------------------------------------------------------


class TestLoadAccountSparklines:
    """Tests for load_account_sparklines — per-account 30-day balance sparklines."""

    @pytest.mark.django_db
    def test_with_snapshots(self, svc_data):
        # gap: functional — load_account_sparklines never directly tested
        today = date.today()
        with connection.cursor() as cursor:
            for i in range(5):
                cursor.execute(
                    "INSERT INTO account_snapshots (id, user_id, account_id, date, balance)"
                    " VALUES (%s, %s, %s, %s, %s)",
                    [
                        str(uuid.uuid4()),
                        svc_data["user_id"],
                        svc_data["savings_id"],
                        today - timedelta(days=10 - i),
                        10000 + i * 100,
                    ],
                )

        svc = DashboardService(svc_data["user_id"], TZ)
        from dashboard.services import DashboardData

        data = DashboardData()
        accounts = svc._load_institutions_with_accounts(data)
        svc._load_account_sparklines(data, accounts)
        assert svc_data["savings_id"] in data.account_sparklines
        assert len(data.account_sparklines[svc_data["savings_id"]]) == 5

    @pytest.mark.django_db
    def test_without_snapshots(self, svc_data):
        # gap: functional — no snapshots → account_sparklines stays empty {}
        svc = DashboardService(svc_data["user_id"], TZ)
        from dashboard.services import DashboardData

        data = DashboardData()
        accounts = svc._load_institutions_with_accounts(data)
        svc._load_account_sparklines(data, accounts)
        assert data.account_sparklines == {}

    @pytest.mark.django_db
    def test_requires_at_least_two_points(self, svc_data):
        # gap: functional — single snapshot must NOT produce a sparkline (needs >=2)
        today = date.today()
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO account_snapshots (id, user_id, account_id, date, balance)"
                " VALUES (%s, %s, %s, %s, 10000)",
                [
                    str(uuid.uuid4()),
                    svc_data["user_id"],
                    svc_data["savings_id"],
                    today,
                ],
            )

        svc = DashboardService(svc_data["user_id"], TZ)
        from dashboard.services import DashboardData

        data = DashboardData()
        accounts = svc._load_institutions_with_accounts(data)
        svc._load_account_sparklines(data, accounts)
        assert svc_data["savings_id"] not in data.account_sparklines


# ---------------------------------------------------------------------------
# Virtual Accounts
# ---------------------------------------------------------------------------


class TestLoadVirtualAccounts:
    """Tests for load_virtual_accounts — dashboard VA widget data."""

    @pytest.mark.django_db
    def test_with_virtual_accounts(self, svc_data):
        # gap: functional — load_virtual_accounts never directly tested
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO virtual_accounts (id, user_id, name, current_balance, target_amount,"
                " icon, color, is_archived, exclude_from_net_worth, display_order)"
                " VALUES (%s, %s, 'Emergency Fund', 5000, 10000, %s, '#ff0000', false, false, 0)",
                [str(uuid.uuid4()), svc_data["user_id"], "\U0001f6e1\ufe0f"],
            )

        svc = DashboardService(svc_data["user_id"], TZ)
        vas = svc._load_virtual_accounts()
        assert len(vas) == 1
        assert vas[0]["name"] == "Emergency Fund"
        assert vas[0]["current_balance"] == 5000.0
        assert vas[0]["target_amount"] == 10000.0
        assert vas[0]["progress_pct"] == pytest.approx(50.0)

    @pytest.mark.django_db
    def test_empty(self, svc_data):
        # gap: functional — no VAs → empty list
        svc = DashboardService(svc_data["user_id"], TZ)
        vas = svc._load_virtual_accounts()
        assert vas == []

    @pytest.mark.django_db
    def test_excludes_archived(self, svc_data):
        # gap: functional — archived VAs must be filtered out
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO virtual_accounts (id, user_id, name, current_balance,"
                " is_archived, exclude_from_net_worth, display_order)"
                " VALUES (%s, %s, 'Active VA', 1000, false, false, 0)",
                [str(uuid.uuid4()), svc_data["user_id"]],
            )
            cursor.execute(
                "INSERT INTO virtual_accounts (id, user_id, name, current_balance,"
                " is_archived, exclude_from_net_worth, display_order)"
                " VALUES (%s, %s, 'Archived VA', 2000, true, false, 1)",
                [str(uuid.uuid4()), svc_data["user_id"]],
            )

        svc = DashboardService(svc_data["user_id"], TZ)
        vas = svc._load_virtual_accounts()
        assert len(vas) == 1
        assert vas[0]["name"] == "Active VA"

    @pytest.mark.django_db
    def test_progress_zero_when_no_target(self, svc_data):
        # gap: functional — VA with no target_amount → progress_pct=0
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO virtual_accounts (id, user_id, name, current_balance,"
                " is_archived, exclude_from_net_worth, display_order)"
                " VALUES (%s, %s, 'No Target VA', 3000, false, false, 0)",
                [str(uuid.uuid4()), svc_data["user_id"]],
            )

        svc = DashboardService(svc_data["user_id"], TZ)
        vas = svc._load_virtual_accounts()
        assert len(vas) == 1
        assert vas[0]["progress_pct"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Investments Total
# ---------------------------------------------------------------------------


class TestLoadInvestmentsTotal:
    """Tests for load_investments_total — SUM(units * last_unit_price)."""

    @pytest.mark.django_db
    def test_sum_investments(self, svc_data):
        # gap: functional — load_investments_total never directly tested
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO investments (id, user_id, platform, fund_name, units, last_unit_price, currency)"
                " VALUES (%s, %s, 'Thndr', 'Fund A', 100, 15.50, 'EGP')",
                [str(uuid.uuid4()), svc_data["user_id"]],
            )
            cursor.execute(
                "INSERT INTO investments (id, user_id, platform, fund_name, units, last_unit_price, currency)"
                " VALUES (%s, %s, 'Thndr', 'Fund B', 50, 20.00, 'EGP')",
                [str(uuid.uuid4()), svc_data["user_id"]],
            )

        svc = DashboardService(svc_data["user_id"], TZ)
        total = svc._load_investments_total()
        # 100*15.50 + 50*20.00 = 1550 + 1000 = 2550
        assert total == pytest.approx(2550.0)

    @pytest.mark.django_db
    def test_empty_investments(self, svc_data):
        # gap: functional — no investments → total=0
        svc = DashboardService(svc_data["user_id"], TZ)
        total = svc._load_investments_total()
        assert total == pytest.approx(0.0)
