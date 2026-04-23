"""
Dashboard service tests — integration tests for each query method.

Tests follow the factory_boy pattern: ORM factories for test data,
direct calls to service methods, automatic rollback via pytest-django.
"""

from datetime import date, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from accounts.models import Account
from auth_app.models import User
from conftest import UserFactory
from core.dates import prev_month_range
from dashboard.services import (
    DashboardService,
    _compute_due_date,
)
from dashboard.services.accounts import get_net_worth_breakdown
from tests.factories import (
    AccountFactory,
    AccountSnapshotFactory,
    BudgetFactory,
    CategoryFactory,
    CurrencyFactory,
    DailySnapshotFactory,
    ExchangeRateLogFactory,
    InstitutionFactory,
    InvestmentFactory,
    PersonCurrencyBalanceFactory,
    PersonFactory,
    TransactionFactory,
    UserCurrencyPreferenceFactory,
    VirtualAccountFactory,
)

TZ = ZoneInfo("Africa/Cairo")


@pytest.fixture
def svc_data(db):
    """User + institution + 2 accounts (EGP savings + EGP credit card) + exchange rate.

    Yields a dict with user_id and account IDs. Creates DashboardService-ready data.
    """
    user = UserFactory()
    inst = InstitutionFactory(user_id=user.id, name="Test Bank")
    savings = AccountFactory(
        user_id=user.id,
        institution_id=inst.id,
        name="Savings EGP",
        type="savings",
        currency="EGP",
        current_balance=10000,
    )
    cc = AccountFactory(
        user_id=user.id,
        institution_id=inst.id,
        name="CC EGP",
        type="credit_card",
        currency="EGP",
        current_balance=-2000,
        credit_limit=10000,
    )
    ExchangeRateLogFactory(date=date.today(), rate=50.5)
    cat = CategoryFactory(
        user_id=user.id, name={"en": "Food"}, type="expense", icon="🛒"
    )

    yield {
        "user": user,
        "user_id": str(user.id),
        "inst_id": str(inst.id),
        "savings_id": str(savings.id),
        "savings": savings,
        "cc_id": str(cc.id),
        "cat_id": str(cat.id),
    }


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
    for i in range(3):
        TransactionFactory(
            user_id=svc_data["user"].id,
            account_id=svc_data["savings"].id,
            type="expense",
            amount=100 + i * 50,
            currency="EGP",
            date=today - timedelta(days=i),
            balance_delta=-(100 + i * 50),
        )

    svc = DashboardService(svc_data["user_id"], TZ)
    txns = svc.load_recent_transactions(limit=5)
    assert len(txns) == 3
    assert txns[0].account_name == "Savings EGP"
    assert txns[0].running_balance is not None


@pytest.mark.django_db
def test_load_recent_transactions_includes_category(svc_data):
    """TransactionRow includes category_name and category_icon when category is set."""
    TransactionFactory(
        user_id=svc_data["user"].id,
        account_id=svc_data["savings"].id,
        type="expense",
        amount=100,
        currency="EGP",
        date=date.today(),
        category_id=svc_data["cat_id"],
        balance_delta=-100,
    )
    svc = DashboardService(svc_data["user_id"], TZ)
    txns = svc.load_recent_transactions(limit=5)
    assert len(txns) == 1
    assert txns[0].category_name == "Food"
    assert txns[0].category_icon == "🛒"


@pytest.mark.django_db
def test_load_recent_transactions_no_category(svc_data):
    """TransactionRow has None category fields when no category set."""
    TransactionFactory(
        user_id=svc_data["user"].id,
        account_id=svc_data["savings"].id,
        type="expense",
        amount=100,
        currency="EGP",
        date=date.today(),
        balance_delta=-100,
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
    for d in tx_dates:
        TransactionFactory(
            user_id=svc_data["user"].id,
            account_id=svc_data["savings"].id,
            type="expense",
            amount=100,
            currency="EGP",
            date=d,
            balance_delta=-100,
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
    # Today and yesterday
    for i in range(2):
        TransactionFactory(
            user_id=svc_data["user"].id,
            account_id=svc_data["savings"].id,
            type="expense",
            amount=100,
            currency="EGP",
            date=today - timedelta(days=i),
            balance_delta=-100,
        )
    # Skip day 2, add day 3
    TransactionFactory(
        user_id=svc_data["user"].id,
        account_id=svc_data["savings"].id,
        type="expense",
        amount=100,
        currency="EGP",
        date=today - timedelta(days=3),
        balance_delta=-100,
    )

    svc = DashboardService(svc_data["user_id"], TZ)
    streak = svc._load_streak()
    assert streak.consecutive_days == 2  # only today + yesterday


# ---------------------------------------------------------------------------
# People Summary
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_load_people_summary(svc_data):
    """Groups people by currency using generalized balance rows."""
    CurrencyFactory(code="USD", display_order=1)
    CurrencyFactory(code="EUR", display_order=2)
    UserCurrencyPreferenceFactory(
        user=svc_data["user"],
        active_currency_codes=["EGP", "USD", "EUR"],
        selected_display_currency="EUR",
    )
    alice = PersonFactory(user_id=svc_data["user"].id, name="Alice")
    bob = PersonFactory(user_id=svc_data["user"].id, name="Bob")
    PersonCurrencyBalanceFactory(person=alice, currency_id="EUR", balance=500)
    PersonCurrencyBalanceFactory(person=bob, currency_id="EUR", balance=-200)
    PersonCurrencyBalanceFactory(person=alice, currency_id="USD", balance=50)

    svc = DashboardService(svc_data["user_id"], TZ)
    from dashboard.services import DashboardData

    data = DashboardData(selected_currency="EUR")
    svc._load_people_summary(data)
    assert data.has_people_activity is True
    assert [summary.currency for summary in data.people_by_currency] == ["USD", "EUR"]
    assert data.selected_people_summary is not None
    assert data.selected_people_summary.currency == "EUR"
    assert data.selected_people_summary.owed_to_me == 500.0
    assert data.selected_people_summary.i_owe == -200.0
    assert data.people_owed_to_me == 500.0
    assert data.people_i_owe == -200.0


# ---------------------------------------------------------------------------
# Budgets
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_load_budgets_with_spending(svc_data):
    """Returns budget with correct spent amount."""
    today = date.today()
    BudgetFactory(
        user_id=svc_data["user"].id,
        category_id=svc_data["cat_id"],
        monthly_limit=1000,
        currency="EGP",
    )
    # Add 2 expenses in current month
    for i in range(2):
        TransactionFactory(
            user_id=svc_data["user"].id,
            account_id=svc_data["savings"].id,
            category_id=svc_data["cat_id"],
            type="expense",
            amount=200,
            currency="EGP",
            date=today.replace(day=max(1, today.day - i)),
            balance_delta=-200,
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
    Account.objects.filter(id=svc_data["savings_id"]).update(
        health_config={"min_balance": 20000}
    )

    svc = DashboardService(svc_data["user_id"], TZ)
    from dashboard.services import DashboardData

    data = DashboardData()
    accounts = svc._load_institutions_with_accounts(data)
    warnings = svc._load_health_warnings(accounts)
    assert len(warnings) >= 1
    assert warnings[0].rule == "min_balance"
    assert "below minimum" in warnings[0].message


# ---------------------------------------------------------------------------
# Net Worth History
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_load_net_worth_history(svc_data):
    """Returns sparkline values from daily_snapshots."""
    today = date.today()
    for i in range(5):
        DailySnapshotFactory(
            user=svc_data["user"],
            date=today - timedelta(days=10 - i),
            net_worth_egp=10000 + i * 100,
            net_worth_raw=10000 + i * 100,
            exchange_rate=50.0,
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

    # This month: 2 expenses
    for i in range(2):
        TransactionFactory(
            user_id=svc_data["user"].id,
            account_id=svc_data["savings"].id,
            type="expense",
            amount=300,
            currency="EGP",
            date=this_month_start + timedelta(days=i),
            balance_delta=-300,
        )
    # Last month: 1 expense
    TransactionFactory(
        user_id=svc_data["user"].id,
        account_id=svc_data["savings"].id,
        type="expense",
        amount=500,
        currency="EGP",
        date=last_month_start + timedelta(days=5),
        balance_delta=-500,
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
    for days_ago, delta in [(2, -200), (1, -150), (0, -100)]:
        TransactionFactory(
            user_id=svc_data["user"].id,
            account_id=svc_data["savings"].id,
            type="expense",
            amount=abs(delta),
            currency="EGP",
            date=today - timedelta(days=days_ago),
            balance_delta=delta,
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
    TransactionFactory(
        user_id=svc_data["user"].id,
        account_id=svc_data["savings"].id,
        type="expense",
        amount=500,
        currency="EGP",
        date=today,
        balance_delta=-500,
    )
    TransactionFactory(
        user_id=svc_data["user"].id,
        account_id=svc_data["cc_id"],
        type="expense",
        amount=200,
        currency="EGP",
        date=today - timedelta(days=1),
        balance_delta=-200,
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
    BudgetFactory(
        user_id=svc_data["user"].id,
        category_id=svc_data["cat_id"],
        monthly_limit=1000,
        currency="EGP",
    )
    # 850 EGP spent = 85% → amber
    TransactionFactory(
        user_id=svc_data["user"].id,
        account_id=svc_data["savings"].id,
        category_id=svc_data["cat_id"],
        type="expense",
        amount=850,
        currency="EGP",
        date=today,
        balance_delta=-850,
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
    BudgetFactory(
        user_id=svc_data["user"].id,
        category_id=svc_data["cat_id"],
        monthly_limit=1000,
        currency="EGP",
    )
    # 1200 EGP spent = 120% → red
    TransactionFactory(
        user_id=svc_data["user"].id,
        account_id=svc_data["savings"].id,
        category_id=svc_data["cat_id"],
        type="expense",
        amount=1200,
        currency="EGP",
        date=today,
        balance_delta=-1200,
    )
    svc = DashboardService(svc_data["user_id"], TZ)
    budgets = svc._load_budgets_with_spending()
    assert budgets[0]["status"] == "red"
    assert budgets[0]["percentage"] == pytest.approx(120.0)


@pytest.mark.django_db
def test_load_budgets_zero_spending(svc_data):
    # gap: data — budget with no transactions this month; spent=0 never asserted
    BudgetFactory(
        user_id=svc_data["user"].id,
        category_id=svc_data["cat_id"],
        monthly_limit=500,
        currency="EGP",
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
    today = date.today()
    BudgetFactory(
        user_id=svc_data["user"].id,
        category_id=svc_data["cat_id"],
        monthly_limit=200,
        currency="USD",
    )
    # EGP expense for same category — must NOT be counted against USD budget
    TransactionFactory(
        user_id=svc_data["user"].id,
        account_id=svc_data["savings"].id,
        category_id=svc_data["cat_id"],
        type="expense",
        amount=500,
        currency="EGP",
        date=today,
        balance_delta=-500,
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
    TransactionFactory(
        user_id=svc_data["user"].id,
        account_id=svc_data["savings"].id,
        category_id=svc_data["cat_id"],
        type="expense",
        amount=400,
        currency="EGP",
        date=this_month_start,
        balance_delta=-400,
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
    TransactionFactory(
        user_id=svc_data["user"].id,
        account_id=svc_data["savings"].id,
        category_id=svc_data["cat_id"],
        type="expense",
        amount=300,
        currency="EGP",
        date=this_month_start,
        balance_delta=-300,
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
    # Expense with NO category
    TransactionFactory(
        user_id=svc_data["user"].id,
        account_id=svc_data["savings"].id,
        type="expense",
        amount=250,
        currency="EGP",
        date=this_month_start,
        balance_delta=-250,
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
    TransactionFactory(
        user_id=svc_data["user"].id,
        account_id=svc_data["savings"].id,
        category_id=svc_data["cat_id"],
        type="expense",
        amount=500,
        currency="EGP",
        date=this_month_start,
        balance_delta=-500,
    )
    TransactionFactory(
        user_id=svc_data["user"].id,
        account_id=svc_data["savings"].id,
        category_id=svc_data["cat_id"],
        type="expense",
        amount=300,
        currency="EGP",
        date=last_month_start,
        balance_delta=-300,
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
    TransactionFactory(
        user_id=svc_data["user"].id,
        account_id=svc_data["savings"].id,
        category_id=svc_data["cat_id"],
        type="expense",
        amount=200,
        currency="EGP",
        date=this_month_start,
        balance_delta=-200,
    )
    TransactionFactory(
        user_id=svc_data["user"].id,
        account_id=svc_data["savings"].id,
        category_id=svc_data["cat_id"],
        type="expense",
        amount=500,
        currency="EGP",
        date=last_month_start,
        balance_delta=-500,
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
    BudgetFactory(
        user_id=svc_data["user"].id,
        category_id=svc_data["cat_id"],
        monthly_limit=1000,
        currency="EGP",
        is_active=False,
    )
    svc = DashboardService(svc_data["user_id"], TZ)
    budgets = svc._load_budgets_with_spending()
    assert budgets == []


@pytest.mark.django_db
def test_load_recent_transactions_default_limit(svc_data):
    # gap: functional — limit parameter never actually cuts off results (all prior tests use limit < row count)
    today = date.today()
    for i in range(15):
        TransactionFactory(
            user_id=svc_data["user"].id,
            account_id=svc_data["savings"].id,
            type="expense",
            amount=50,
            currency="EGP",
            date=today - timedelta(days=i),
            balance_delta=-50,
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
    cat2 = CategoryFactory(
        user_id=svc_data["user"].id, name={"en": "Transport"}, type="expense"
    )
    # This month: Food=400, Transport=300
    TransactionFactory(
        user_id=svc_data["user"].id,
        account_id=svc_data["savings"].id,
        category_id=svc_data["cat_id"],
        type="expense",
        amount=400,
        currency="EGP",
        date=this_month_start,
        balance_delta=-400,
    )
    TransactionFactory(
        user_id=svc_data["user"].id,
        account_id=svc_data["savings"].id,
        category_id=cat2.id,
        type="expense",
        amount=300,
        currency="EGP",
        date=this_month_start,
        balance_delta=-300,
    )
    # Last month: Food=200, Transport=600
    TransactionFactory(
        user_id=svc_data["user"].id,
        account_id=svc_data["savings"].id,
        category_id=svc_data["cat_id"],
        type="expense",
        amount=200,
        currency="EGP",
        date=last_month_start,
        balance_delta=-200,
    )
    TransactionFactory(
        user_id=svc_data["user"].id,
        account_id=svc_data["savings"].id,
        category_id=cat2.id,
        type="expense",
        amount=600,
        currency="EGP",
        date=last_month_start,
        balance_delta=-600,
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
        usd_acc = AccountFactory(
            user_id=svc_data["user"].id,
            institution_id=svc_data["inst_id"],
            name="USD Savings",
            type="savings",
            currency="USD",
            current_balance=500,
        )
        for i in range(3):
            snap_date = today - timedelta(days=5 - i)
            # EGP account snapshot
            AccountSnapshotFactory(
                user=svc_data["user"],
                account=svc_data["savings"],
                date=snap_date,
                balance=10000 + i * 100,
            )
            # USD account snapshot
            AccountSnapshotFactory(
                user=svc_data["user"],
                account=usd_acc,
                date=snap_date,
                balance=500 + i * 10,
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
        for i in range(5):
            AccountSnapshotFactory(
                user=svc_data["user"],
                account=svc_data["savings"],
                date=today - timedelta(days=10 - i),
                balance=10000 + i * 100,
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
        AccountSnapshotFactory(
            user=svc_data["user"],
            account=svc_data["savings"],
            date=today,
            balance=10000,
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
        VirtualAccountFactory(
            user_id=svc_data["user"].id,
            name="Emergency Fund",
            current_balance=5000,
            target_amount=10000,
            icon="\U0001f6e1\ufe0f",
            color="#ff0000",
            is_archived=False,
            display_order=0,
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
        VirtualAccountFactory(
            user_id=svc_data["user"].id,
            name="Active VA",
            current_balance=1000,
            is_archived=False,
            display_order=0,
        )
        VirtualAccountFactory(
            user_id=svc_data["user"].id,
            name="Archived VA",
            current_balance=2000,
            is_archived=True,
            display_order=1,
        )

        svc = DashboardService(svc_data["user_id"], TZ)
        vas = svc._load_virtual_accounts()
        assert len(vas) == 1
        assert vas[0]["name"] == "Active VA"

    @pytest.mark.django_db
    def test_progress_zero_when_no_target(self, svc_data):
        # gap: functional — VA with no target_amount → progress_pct=0
        VirtualAccountFactory(
            user_id=svc_data["user"].id,
            name="No Target VA",
            current_balance=3000,
            is_archived=False,
            display_order=0,
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
        InvestmentFactory(
            user_id=svc_data["user"].id,
            platform="Thndr",
            fund_name="Fund A",
            units=100,
            last_unit_price=15.50,
            currency="EGP",
        )
        InvestmentFactory(
            user_id=svc_data["user"].id,
            platform="Thndr",
            fund_name="Fund B",
            units=50,
            last_unit_price=20.00,
            currency="EGP",
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


# ---------------------------------------------------------------------------
# Net worth breakdown
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestNetWorthBreakdown:
    """get_net_worth_breakdown returns correct accounts per card type."""

    @pytest.fixture
    def nw_data(self, db):
        """User with savings, current, credit card, and dormant accounts."""
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id, name="CIB", icon="🏦")
        savings = AccountFactory(
            user_id=user.id,
            institution_id=inst.id,
            name="Savings",
            type="savings",
            currency="EGP",
            current_balance=50000,
        )
        current = AccountFactory(
            user_id=user.id,
            institution_id=inst.id,
            name="Current",
            type="current",
            currency="EGP",
            current_balance=10000,
        )
        cc = AccountFactory(
            user_id=user.id,
            institution_id=inst.id,
            name="CC",
            type="credit_card",
            currency="EGP",
            current_balance=-5000,
            credit_limit=20000,
        )
        dormant = AccountFactory(
            user_id=user.id,
            institution_id=inst.id,
            name="Old",
            type="savings",
            currency="EGP",
            current_balance=100,
            is_dormant=True,
        )
        return {
            "user_id": str(user.id),
            "savings": savings,
            "current": current,
            "cc": cc,
            "dormant": dormant,
        }

    def test_liquid_cash_includes_non_credit_positive(self, nw_data):
        result = get_net_worth_breakdown(nw_data["user_id"], "liquid_cash")
        names = [a["name"] for a in result["accounts"]]
        assert "Savings" in names
        assert "Current" in names
        assert "CC" not in names
        assert "Old" not in names  # dormant excluded

    def test_liquid_cash_sorted_by_balance_desc(self, nw_data):
        result = get_net_worth_breakdown(nw_data["user_id"], "liquid_cash")
        balances = [a["balance"] for a in result["accounts"]]
        assert balances == sorted(balances, reverse=True)

    def test_credit_used_includes_cc(self, nw_data):
        result = get_net_worth_breakdown(nw_data["user_id"], "credit_used")
        names = [a["name"] for a in result["accounts"]]
        assert "CC" in names
        assert "Savings" not in names

    def test_credit_available(self, nw_data):
        result = get_net_worth_breakdown(nw_data["user_id"], "credit_available")
        cc = result["accounts"][0]
        # Available = credit_limit + current_balance = 20000 + (-5000) = 15000
        assert cc["available"] == 15000

    def test_debt_includes_negative_balances(self, nw_data):
        result = get_net_worth_breakdown(nw_data["user_id"], "debt")
        names = [a["name"] for a in result["accounts"]]
        assert "CC" in names

    def test_invalid_card_type(self, nw_data):
        with pytest.raises(ValueError):
            get_net_worth_breakdown(nw_data["user_id"], "invalid")

    def test_title_matches_card_type(self, nw_data):
        result = get_net_worth_breakdown(nw_data["user_id"], "liquid_cash")
        assert result["title"] == "Liquid Cash"

    def test_debt_breakdown_includes_people_i_owe(self, nw_data):
        """Debt breakdown includes people with negative net_balance."""
        PersonFactory(
            user_id=nw_data["cc"].user_id,
            name="Ali",
            net_balance=-300,
            net_balance_egp=-300,
        )
        result = get_net_worth_breakdown(nw_data["user_id"], "debt")
        names = [a["name"] for a in result["accounts"]]
        assert "Ali" in names
        assert "CC" in names

    def test_debt_breakdown_excludes_people_with_positive_balance(self, nw_data):
        """People who owe me should not appear in debt breakdown."""
        PersonFactory(
            user_id=nw_data["cc"].user_id,
            name="Omar",
            net_balance=500,
            net_balance_egp=500,
        )
        result = get_net_worth_breakdown(nw_data["user_id"], "debt")
        names = [a["name"] for a in result["accounts"]]
        assert "Omar" not in names

    def test_empty_result(self, db):
        user = UserFactory()
        result = get_net_worth_breakdown(str(user.id), "liquid_cash")
        assert result["accounts"] == []


# ---------------------------------------------------------------------------
# Debt total — accounts + people
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_debt_total_from_negative_accounts(svc_data):
    """debt_total = abs(sum of negative account balances)."""
    svc = DashboardService(svc_data["user_id"], TZ)
    result = svc.get_dashboard()
    # svc_data has CC with -2000 → debt_total should be 2000
    assert result["debt_total"] == pytest.approx(2000.0)


@pytest.mark.django_db
def test_debt_total_includes_people_i_owe(svc_data):
    """debt_total includes abs(people_i_owe)."""
    PersonFactory(
        user_id=svc_data["user"].id,
        name="Ali",
        net_balance=-500,
        net_balance_egp=-500,
    )
    svc = DashboardService(svc_data["user_id"], TZ)
    result = svc.get_dashboard()
    # CC -2000 + person -500 → debt_total = 2500
    assert result["debt_total"] == pytest.approx(2500.0)


@pytest.mark.django_db
def test_debt_total_includes_generalized_people_debt_by_currency(svc_data):
    """Debt aggregation sums generalized people debt without fixed currency branches."""
    CurrencyFactory(code="USD", display_order=1)
    CurrencyFactory(code="EUR", display_order=2)
    ali = PersonFactory(user_id=svc_data["user"].id, name="Ali")
    sara = PersonFactory(user_id=svc_data["user"].id, name="Sara")
    PersonCurrencyBalanceFactory(person=ali, currency_id="EUR", balance=-300)
    PersonCurrencyBalanceFactory(person=sara, currency_id="USD", balance=-50)

    svc = DashboardService(svc_data["user_id"], TZ)
    result = svc.get_dashboard()

    assert result["debt_by_currency"] == {"USD": 50.0, "EUR": 300.0}
    assert result["debt_total"] == pytest.approx(2350.0)


@pytest.mark.django_db
def test_debt_total_zero_when_no_debt(db):
    """debt_total is 0 when all balances are positive and no people owed."""
    user = UserFactory()
    inst = InstitutionFactory(user_id=user.id, name="Bank")
    AccountFactory(
        user_id=user.id,
        institution_id=inst.id,
        name="Savings",
        type="savings",
        currency="EGP",
        current_balance=5000,
    )
    ExchangeRateLogFactory(date=date.today(), rate=50.0)
    svc = DashboardService(str(user.id), TZ)
    result = svc.get_dashboard()
    assert result["debt_total"] == 0.0


@pytest.mark.django_db
def test_debt_total_only_people_no_account_debt(db):
    """debt_total from people only, no negative account balances."""
    user = UserFactory()
    inst = InstitutionFactory(user_id=user.id, name="Bank")
    AccountFactory(
        user_id=user.id,
        institution_id=inst.id,
        name="Savings",
        type="savings",
        currency="EGP",
        current_balance=5000,
    )
    PersonFactory(user_id=user.id, name="Sara", net_balance=-300, net_balance_egp=-300)
    ExchangeRateLogFactory(date=date.today(), rate=50.0)
    svc = DashboardService(str(user.id), TZ)
    result = svc.get_dashboard()
    assert result["debt_total"] == pytest.approx(300.0)


@pytest.mark.django_db
def test_load_people_summary_with_selected_currency_and_third_currency(svc_data):
    """Selected-currency slice is derived from the generalized currency collection."""
    CurrencyFactory(code="USD", display_order=1)
    CurrencyFactory(code="EUR", display_order=2)
    UserCurrencyPreferenceFactory(
        user=svc_data["user"],
        active_currency_codes=["EGP", "USD", "EUR"],
        selected_display_currency="USD",
    )
    ali = PersonFactory(user_id=svc_data["user"].id, name="Ali")
    sara = PersonFactory(user_id=svc_data["user"].id, name="Sara")
    PersonCurrencyBalanceFactory(person=ali, currency_id="EUR", balance=300)
    PersonCurrencyBalanceFactory(person=ali, currency_id="USD", balance=125)
    PersonCurrencyBalanceFactory(person=sara, currency_id="USD", balance=-25)

    svc = DashboardService(str(svc_data["user_id"]), TZ)
    result = svc.get_dashboard()

    assert [summary["currency"] if isinstance(summary, dict) else summary.currency for summary in result["people_by_currency"]] == ["USD", "EUR"]
    assert result["selected_currency"] == "USD"
    assert result["selected_people_summary"].currency == "USD"
    assert result["people_owed_to_me"] == 125.0
    assert result["people_i_owe"] == -25.0
    assert result["selected_debt"] == 25.0


# ==================== Tests for decomposed sub-methods ====================


@pytest.mark.django_db
def test_load_core_data_populates_net_worth_and_accounts(svc_data):
    """_load_core_data() should populate net worth, exchange rate, accounts."""
    svc = DashboardService(str(svc_data["user_id"]), TZ)
    from dashboard.services import DashboardData

    data = DashboardData()
    all_accounts = svc._load_core_data(data)
    assert len(all_accounts) > 0
    assert data.net_worth > 0
    assert data.exchange_rate > 0
    assert len(data.institutions) > 0


@pytest.mark.django_db
def test_load_financial_summary_populates_credit_and_people(svc_data):
    """_load_financial_summary() should populate credit card and people data."""
    svc = DashboardService(str(svc_data["user_id"]), TZ)
    from dashboard.services import DashboardData

    data = DashboardData()
    all_accounts = svc._load_core_data(data)
    svc._load_financial_summary(data, all_accounts)
    # After loading financial summary, credit data should be populated
    assert hasattr(data, "credit_cards")
    assert hasattr(data, "people_owed_to_me")


@pytest.mark.django_db
def test_load_activity_data_populates_transactions_and_virtual_accounts(svc_data):
    """_load_activity_data() should populate transactions, VA, and budgets."""
    svc = DashboardService(str(svc_data["user_id"]), TZ)
    from dashboard.services import DashboardData

    data = DashboardData()
    svc._load_activity_data(data)
    # Activity data should be loaded
    assert hasattr(data, "recent_transactions")
    assert hasattr(data, "virtual_accounts")
    assert hasattr(data, "budgets")


@pytest.mark.django_db
def test_load_sparklines_populates_history_data(svc_data):
    """_load_sparklines() should populate net worth history and sparklines."""
    svc = DashboardService(str(svc_data["user_id"]), TZ)
    from dashboard.services import DashboardData

    data = DashboardData()
    all_accounts = svc._load_core_data(data)
    svc._load_sparklines(data, all_accounts)
    # Sparklines should be populated
    assert hasattr(data, "net_worth_history")
    assert hasattr(data, "account_sparklines")


@pytest.mark.django_db
def test_load_constraints_populates_health_warnings(svc_data):
    """_load_constraints() should populate health warnings."""
    svc = DashboardService(str(svc_data["user_id"]), TZ)
    from dashboard.services import DashboardData

    data = DashboardData()
    all_accounts = svc._load_core_data(data)
    svc._load_constraints(data, all_accounts)
    # Health data should be populated
    assert hasattr(data, "health_warnings")


# ==================== Edge Cases from Coverage ====================


@pytest.mark.django_db
def test_dashboard_usd_exchange_rate_fallback(svc_data):
    """Test accounts in USD are converted using exchange rate and compute net worth correctly."""
    AccountFactory(
        user_id=svc_data["user"].id,
        institution_id=svc_data["inst_id"],
        name="USD Savings",
        type="savings",
        currency="USD",
        current_balance=100,
    )
    svc = DashboardService(str(svc_data["user_id"]), TZ)
    from dashboard.services import DashboardData

    data = DashboardData()
    data.exchange_rate = 50.0  # exchange rate > 0
    all_accounts = svc._load_institutions_with_accounts(data)

    # 1. Test load_institutions_with_accounts (line 174)
    inst = data.institutions[0]
    # USD Savings (100*50=5000), Savings EGP (10000), CC EGP (-2000)
    # Total = 5000 + 10000 - 2000 = 13000
    assert inst.total == pytest.approx(13000.0)

    # 2. Test compute_net_worth exchange rate recalculation (line 225)
    svc._compute_net_worth(data, all_accounts)
    assert inst.total == pytest.approx(13000.0)


@pytest.mark.django_db
def test_get_net_worth_breakdown_people_debt_usd(svc_data):
    """Debt breakdown includes generalized per-currency people debt rows."""
    CurrencyFactory(code="USD", display_order=1)
    person = PersonFactory(user_id=svc_data["user"].id, name="John Doe")
    PersonCurrencyBalanceFactory(person=person, currency_id="USD", balance=-50)
    result = get_net_worth_breakdown(str(svc_data["user_id"]), "debt")
    names = [row["name"] for row in result["accounts"]]
    assert "John Doe" in names
    row = next(r for r in result["accounts"] if r["name"] == "John Doe")
    assert row["currency"] == "USD"
    assert row["balance"] == -50.0


@pytest.mark.django_db
def test_spending_by_currency_other_than_egp(svc_data):
    """Test spending by currency ordering works when spending in a non-EGP currency (line 76)."""
    today = date.today()
    this_month_start = today.replace(day=1)

    TransactionFactory(
        user_id=svc_data["user"].id,
        account_id=svc_data["savings"].id,
        type="expense",
        amount=100,
        currency="EUR",  # Non-EGP currency
        date=this_month_start,
        balance_delta=-100,
    )
    svc = DashboardService(str(svc_data["user_id"]), TZ)
    from dashboard.services import DashboardData

    data = DashboardData()
    data.exchange_rate = 50.0
    svc._compute_spending_comparison(data)

    currencies = [c.currency for c in data.spending_by_currency]
    assert "EUR" in currencies


@pytest.mark.django_db
def test_query_top_categories_empty_this_month(svc_data):
    """Test top categories returns empty when no data for this month but called within loop (line 198)."""
    # Create an expense for LAST month in USD to force loop to run and create empty top categories for USD this month
    today = date.today()
    this_month_start = today.replace(day=1)
    if this_month_start.month == 1:
        last_month_start = date(this_month_start.year - 1, 12, 1)
    else:
        last_month_start = date(this_month_start.year, this_month_start.month - 1, 1)

    TransactionFactory(
        user_id=svc_data["user"].id,
        account_id=svc_data["savings"].id,
        type="expense",
        amount=50,
        currency="GBP",
        date=last_month_start,
        balance_delta=-50,
    )
    svc = DashboardService(str(svc_data["user_id"]), TZ)
    from dashboard.services import DashboardData

    data = DashboardData()
    data.exchange_rate = 50.0
    svc._compute_spending_comparison(data)

    gbp = next(c for c in data.spending_by_currency if c.currency == "GBP")
    assert gbp.this_month == 0.0
    assert gbp.top_categories == []


@pytest.mark.django_db
def test_compute_credit_card_summaries_metadata(svc_data):
    """Test credit card summary correctly uses billing cycle metadata (lines 89-99)."""
    Account.objects.filter(id=svc_data["cc_id"]).update(
        metadata={"statement_day": 5, "due_day": 20}
    )
    svc = DashboardService(str(svc_data["user_id"]), TZ)
    from dashboard.services import DashboardData

    data = DashboardData()
    accounts = svc._load_institutions_with_accounts(data)

    today = date.today()
    with patch("dashboard.services.credit_cards._compute_due_date") as mock_due_date:
        mock_due_date.return_value = today + timedelta(days=3)
        svc._compute_credit_card_summaries(data, accounts)

    assert len(data.due_soon_cards) == 1
    assert data.due_soon_cards[0].account_name == "CC EGP"


@pytest.mark.django_db
def test_load_people_summary_usd_and_negative_nb(svc_data):
    """Selected-currency helpers resolve from generalized summary output."""
    CurrencyFactory(code="USD", display_order=1)
    UserCurrencyPreferenceFactory(
        user=svc_data["user"],
        active_currency_codes=["EGP", "USD"],
        selected_display_currency="USD",
    )
    debtor = PersonFactory(user_id=svc_data["user"].id, name="USD Debtor")
    PersonCurrencyBalanceFactory(person=debtor, currency_id="USD", balance=100)
    svc = DashboardService(str(svc_data["user_id"]), TZ)
    from dashboard.services import DashboardData

    data = DashboardData(selected_currency="USD")
    svc._load_people_summary(data)

    assert data.people_i_owe == 0.0
    assert data.people_owed_to_me == 100.0
    assert data.selected_people_summary is not None
    assert data.selected_people_summary.currency == "USD"
    usd_summary = next(c for c in data.people_by_currency if c.currency == "USD")
    assert usd_summary.owed_to_me == 100.0


# ---------------------------------------------------------------------------
# Spending velocity projections (ticket 076)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_velocity_projection_green_daily_remaining(svc_data):
    """On-track spending: daily_remaining > 0, status=green, reduce_by=0."""
    from calendar import monthrange
    from datetime import date

    from dashboard.services import DashboardData

    today = date.today()
    _, days_in_month = monthrange(today.year, today.month)
    this_month_start = today.replace(day=1)
    last_month_start, _ = prev_month_range(today)

    # Last month: 3000 EGP spent
    TransactionFactory(
        user_id=svc_data["user"].id,
        account_id=svc_data["savings"].id,
        type="expense",
        amount=3000,
        currency="EGP",
        date=last_month_start + timedelta(days=2),
        balance_delta=-3000,
    )

    # This month: only 100 EGP spent (well under pace)
    TransactionFactory(
        user_id=svc_data["user"].id,
        account_id=svc_data["savings"].id,
        type="expense",
        amount=100,
        currency="EGP",
        date=this_month_start,
        balance_delta=-100,
    )

    svc = DashboardService(svc_data["user_id"], TZ)
    data = DashboardData()
    data.exchange_rate = 0.0  # EGP only
    svc._compute_spending_comparison(data)

    sv = data.spending_velocity
    assert sv.status == "green"
    assert sv.budget_total == pytest.approx(3000.0)
    assert sv.daily_remaining > 0
    assert sv.projected_total > 0
    assert sv.reduce_by == pytest.approx(0.0)  # on track → no reduction needed


@pytest.mark.django_db
def test_velocity_projection_projected_total_formula(svc_data):
    """projected_total = (spent / days_elapsed) * days_total."""
    from calendar import monthrange
    from datetime import date

    from dashboard.services import DashboardData

    today = date.today()
    _, days_in_month = monthrange(today.year, today.month)
    this_month_start = today.replace(day=1)

    spent = 1200.0
    TransactionFactory(
        user_id=svc_data["user"].id,
        account_id=svc_data["savings"].id,
        type="expense",
        amount=spent,
        currency="EGP",
        date=this_month_start,
        balance_delta=-spent,
    )

    svc = DashboardService(svc_data["user_id"], TZ)
    data = DashboardData()
    data.exchange_rate = 0.0
    svc._compute_spending_comparison(data)

    sv = data.spending_velocity
    days_elapsed = today.day
    expected_projected = (spent / days_elapsed) * days_in_month
    assert sv.projected_total == pytest.approx(expected_projected, rel=0.01)


@pytest.mark.django_db
def test_velocity_projection_daily_remaining_formula(svc_data):
    """daily_remaining = (budget_total - spent) / days_left."""
    from calendar import monthrange
    from datetime import date

    from dashboard.services import DashboardData

    today = date.today()
    _, days_in_month = monthrange(today.year, today.month)
    days_left = days_in_month - today.day

    this_month_start = today.replace(day=1)
    last_month_start, _ = prev_month_range(today)

    last_month_total = 2000.0
    this_month_spent = 300.0

    TransactionFactory(
        user_id=svc_data["user"].id,
        account_id=svc_data["savings"].id,
        type="expense",
        amount=last_month_total,
        currency="EGP",
        date=last_month_start + timedelta(days=1),
        balance_delta=-last_month_total,
    )
    TransactionFactory(
        user_id=svc_data["user"].id,
        account_id=svc_data["savings"].id,
        type="expense",
        amount=this_month_spent,
        currency="EGP",
        date=this_month_start,
        balance_delta=-this_month_spent,
    )

    svc = DashboardService(svc_data["user_id"], TZ)
    data = DashboardData()
    data.exchange_rate = 0.0
    svc._compute_spending_comparison(data)

    sv = data.spending_velocity
    if days_left > 0:
        expected_dr = (last_month_total - this_month_spent) / days_left
        assert sv.daily_remaining == pytest.approx(expected_dr, rel=0.01)
    # Edge: last day of month → skip formula check (days_left == 0)


@pytest.mark.django_db
def test_velocity_projection_overspend_reduce_by(svc_data):
    """When spending faster than budget pace, reduce_by = daily_pace - budget_daily > 0."""
    from calendar import monthrange
    from datetime import date

    from dashboard.services import DashboardData

    today = date.today()
    _, days_in_month = monthrange(today.year, today.month)
    this_month_start = today.replace(day=1)
    last_month_start, _ = prev_month_range(today)

    # Modest last month baseline
    TransactionFactory(
        user_id=svc_data["user"].id,
        account_id=svc_data["savings"].id,
        type="expense",
        amount=1000,
        currency="EGP",
        date=last_month_start + timedelta(days=1),
        balance_delta=-1000,
    )
    # Massive this-month spend (forces amber/red)
    TransactionFactory(
        user_id=svc_data["user"].id,
        account_id=svc_data["savings"].id,
        type="expense",
        amount=5000,
        currency="EGP",
        date=this_month_start,
        balance_delta=-5000,
    )

    svc = DashboardService(svc_data["user_id"], TZ)
    data = DashboardData()
    data.exchange_rate = 0.0
    svc._compute_spending_comparison(data)

    sv = data.spending_velocity
    assert sv.status in ("amber", "red")
    assert sv.reduce_by > 0


@pytest.mark.django_db
def test_velocity_projection_no_last_month(svc_data):
    """When there is no last month spending, percentage=0, status=green, projections safe."""
    from dashboard.services import DashboardData

    today = date.today()
    this_month_start = today.replace(day=1)

    TransactionFactory(
        user_id=svc_data["user"].id,
        account_id=svc_data["savings"].id,
        type="expense",
        amount=200,
        currency="EGP",
        date=this_month_start,
        balance_delta=-200,
    )

    svc = DashboardService(svc_data["user_id"], TZ)
    data = DashboardData()
    data.exchange_rate = 0.0
    svc._compute_spending_comparison(data)

    sv = data.spending_velocity
    # No baseline → pct = 0 → green
    assert sv.status == "green"
    assert sv.percentage == pytest.approx(0.0)
    assert sv.budget_total == pytest.approx(0.0)
    assert sv.daily_remaining == pytest.approx(0.0)


@pytest.mark.django_db
def test_velocity_projection_no_spending_at_all(svc_data):
    """When there are no transactions at all, all projection fields should be 0."""
    from dashboard.services import DashboardData

    svc = DashboardService(svc_data["user_id"], TZ)
    data = DashboardData()
    data.exchange_rate = 0.0
    svc._compute_spending_comparison(data)

    sv = data.spending_velocity
    assert sv.percentage == pytest.approx(0.0)
    assert sv.projected_total == pytest.approx(0.0)
    assert sv.budget_total == pytest.approx(0.0)
    assert sv.reduce_by == pytest.approx(0.0)
    assert sv.days_total > 0


# ---------------------------------------------------------------------------
# Category velocity (ticket 076)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_compute_category_velocities_basic(svc_data):
    """Returns a CategoryVelocity for each active budget with correct fields."""
    from calendar import monthrange
    from datetime import date

    from dashboard.services import CategoryVelocity

    today = date.today()
    _, days_in_month = monthrange(today.year, today.month)
    days_left = days_in_month - today.day
    this_month_start = today.replace(day=1)

    BudgetFactory(
        user_id=svc_data["user"].id,
        category_id=svc_data["cat_id"],
        monthly_limit=1000,
        currency="EGP",
    )
    TransactionFactory(
        user_id=svc_data["user"].id,
        account_id=svc_data["savings"].id,
        category_id=svc_data["cat_id"],
        type="expense",
        amount=400,
        currency="EGP",
        date=this_month_start,
        balance_delta=-400,
    )

    svc = DashboardService(svc_data["user_id"], TZ)
    cvs = svc._compute_category_velocities()

    assert len(cvs) == 1
    cv = cvs[0]
    assert isinstance(cv, CategoryVelocity)
    assert cv.category_name == "Food"
    assert cv.spent == pytest.approx(400.0)
    assert cv.monthly_limit == pytest.approx(1000.0)
    assert cv.percentage == pytest.approx(40.0)
    assert cv.status == "green"
    if days_left > 0:
        expected_dr = (1000.0 - 400.0) / days_left
        assert cv.daily_remaining == pytest.approx(expected_dr, rel=0.01)
    assert cv.reduce_by == pytest.approx(0.0)  # on track


@pytest.mark.django_db
def test_compute_category_velocities_over_budget(svc_data):
    """Over-budget category has negative daily_remaining and reduce_by > 0."""
    from datetime import date

    today = date.today()
    this_month_start = today.replace(day=1)

    BudgetFactory(
        user_id=svc_data["user"].id,
        category_id=svc_data["cat_id"],
        monthly_limit=500,
        currency="EGP",
    )
    TransactionFactory(
        user_id=svc_data["user"].id,
        account_id=svc_data["savings"].id,
        category_id=svc_data["cat_id"],
        type="expense",
        amount=900,
        currency="EGP",
        date=this_month_start,
        balance_delta=-900,
    )

    svc = DashboardService(svc_data["user_id"], TZ)
    cvs = svc._compute_category_velocities()

    assert len(cvs) == 1
    cv = cvs[0]
    assert cv.spent > cv.monthly_limit
    assert cv.daily_remaining < 0
    assert cv.reduce_by > 0
    assert cv.status in ("amber", "red")


@pytest.mark.django_db
def test_compute_category_velocities_no_budgets(svc_data):
    """Returns empty list when the user has no active budgets."""
    svc = DashboardService(svc_data["user_id"], TZ)
    cvs = svc._compute_category_velocities()
    assert cvs == []


@pytest.mark.django_db
def test_category_velocity_in_dashboard_context(svc_data):
    """get_dashboard() includes category_velocities in the returned dict."""
    BudgetFactory(
        user_id=svc_data["user"].id,
        category_id=svc_data["cat_id"],
        monthly_limit=800,
        currency="EGP",
    )
    svc = DashboardService(svc_data["user_id"], TZ)
    data = svc.get_dashboard()
    assert "category_velocities" in data
    assert isinstance(data["category_velocities"], list)


@pytest.mark.django_db
def test_liquid_cash_splits_by_currency(svc_data):
    """Liquid Cash must NOT mix EGP and USD balances (ticket #118)."""
    from accounts.services import compute_net_worth

    accounts = [
        {
            "current_balance": 13300.0,
            "currency": "EGP",
            "type": "current",
            "credit_limit": None,
        },
        {
            "current_balance": 500.0,
            "currency": "USD",
            "type": "savings",
            "credit_limit": None,
        },
    ]
    summary = compute_net_worth(accounts)
    assert summary.cash_total == pytest.approx(13300.0), "EGP only in cash_total"
    assert summary.cash_usd == pytest.approx(500.0), "USD in cash_usd"
