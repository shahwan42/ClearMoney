"""
Cash flow forecast service tests.

Tests run against the real database with --reuse-db.
"""

from datetime import date, timedelta
from zoneinfo import ZoneInfo

import pytest

from accounts.models import Account
from conftest import SessionFactory, UserFactory
from core.dates import month_range
from dashboard.services.forecast import ForecastService
from recurring.models import RecurringRule
from tests.factories import AccountFactory, CategoryFactory, InstitutionFactory

TZ = ZoneInfo("Africa/Cairo")


@pytest.fixture
def forecast_data(db):
    """User + institution + accounts + recurring rules for forecast tests."""
    user = UserFactory()
    SessionFactory(user=user)
    user_id = str(user.id)

    inst = InstitutionFactory(user_id=user.id)

    # Main account with current balance
    main_account = AccountFactory(
        user_id=user.id,
        institution_id=inst.id,
        name="Main Checking",
        currency="EGP",
        current_balance=15000.0,
        initial_balance=15000.0,
    )

    # Savings account
    savings_account = AccountFactory(
        user_id=user.id,
        institution_id=inst.id,
        name="Savings",
        currency="EGP",
        current_balance=5000.0,
        initial_balance=5000.0,
    )

    # Category for expenses
    cat = CategoryFactory(user_id=user.id, name={"en": "Bills"}, type="expense")

    yield {
        "user_id": user_id,
        "main_account_id": str(main_account.id),
        "savings_account_id": str(savings_account.id),
        "category_id": str(cat.id),
    }


def _svc(user_id: str) -> ForecastService:
    return ForecastService(user_id, TZ)


def _make_template(data: dict, **overrides) -> dict:
    """Build a template_transaction dict for tests."""
    tmpl = {
        "type": "expense",
        "amount": 100.0,
        "currency": "EGP",
        "account_id": data["main_account_id"],
        "category_id": data["category_id"],
        "note": "Monthly bill",
    }
    tmpl.update(overrides)
    return tmpl


def _forecast_due_date(days: int = 1) -> date:
    """Return a due date inside the service's current-month forecast window."""
    today = date.today()
    _, month_end = month_range(today)
    return min(today + timedelta(days=days), month_end)


# ---------------------------------------------------------------------------
# calculate_forecast - basic functionality
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCalculateForecast:
    def test_empty_no_rules(self, forecast_data):
        """Forecast with no recurring rules returns current balance unchanged."""
        svc = _svc(forecast_data["user_id"])
        forecast = svc.calculate_forecast()

        # Current balance = 15000 + 5000 = 20000
        assert forecast.current_balance == 20000.0
        assert forecast.projected_balance == 20000.0
        assert forecast.change == 0.0
        assert len(forecast.days) > 0
        assert not forecast.has_warning

    def test_with_income_rule(self, forecast_data):
        """Forecast includes expected income from recurring rules."""
        svc = _svc(forecast_data["user_id"])

        # Create income rule for next week
        RecurringRule.objects.create(
            user_id=forecast_data["user_id"],
            template_transaction=_make_template(
                forecast_data, type="income", amount=5000.0, note="Salary"
            ),
            frequency="monthly",
            next_due_date=_forecast_due_date(),
            is_active=True,
            auto_confirm=False,
        )

        forecast = svc.calculate_forecast()

        # Should have increased balance
        assert forecast.projected_balance > forecast.current_balance
        assert forecast.income_total == 5000.0
        assert forecast.change == 5000.0

    def test_with_expense_rule(self, forecast_data):
        """Forecast deducts expected expenses from recurring rules."""
        svc = _svc(forecast_data["user_id"])

        # Create expense rule for next week
        RecurringRule.objects.create(
            user_id=forecast_data["user_id"],
            template_transaction=_make_template(
                forecast_data, type="expense", amount=500.0, note="Netflix"
            ),
            frequency="monthly",
            next_due_date=_forecast_due_date(),
            is_active=True,
            auto_confirm=False,
        )

        forecast = svc.calculate_forecast()

        # Should have decreased balance
        assert forecast.projected_balance < forecast.current_balance
        assert forecast.expense_total == 500.0
        assert forecast.change == -500.0

    def test_with_mixed_rules(self, forecast_data):
        """Forecast handles both income and expense rules."""
        svc = _svc(forecast_data["user_id"])

        # Income rule
        RecurringRule.objects.create(
            user_id=forecast_data["user_id"],
            template_transaction=_make_template(
                forecast_data, type="income", amount=10000.0, note="Salary"
            ),
            frequency="monthly",
            next_due_date=date.today() + timedelta(days=1),
            is_active=True,
            auto_confirm=False,
        )

        # Expense rule
        RecurringRule.objects.create(
            user_id=forecast_data["user_id"],
            template_transaction=_make_template(
                forecast_data, type="expense", amount=2000.0, note="Rent"
            ),
            frequency="monthly",
            next_due_date=date.today() + timedelta(days=2),
            is_active=True,
            auto_confirm=False,
        )

        forecast = svc.calculate_forecast()

        # Net change = 10000 - 2000 = 8000
        assert forecast.income_total == 10000.0
        assert forecast.expense_total == 2000.0
        assert forecast.change == 8000.0

    def test_single_account_forecast(self, forecast_data):
        """Forecast can be scoped to a single account."""
        svc = _svc(forecast_data["user_id"])

        # Income rule tied to main account
        RecurringRule.objects.create(
            user_id=forecast_data["user_id"],
            template_transaction=_make_template(
                forecast_data, type="income", amount=3000.0
            ),
            frequency="monthly",
            next_due_date=_forecast_due_date(),
            is_active=True,
            auto_confirm=False,
        )

        # Forecast only main account (15000 balance)
        forecast = svc.calculate_forecast(account_id=forecast_data["main_account_id"])

        assert forecast.current_balance == 15000.0
        assert forecast.projected_balance == 18000.0

    def test_inactive_rules_excluded(self, forecast_data):
        """Inactive rules are not included in forecast."""
        svc = _svc(forecast_data["user_id"])

        # Inactive income rule
        RecurringRule.objects.create(
            user_id=forecast_data["user_id"],
            template_transaction=_make_template(
                forecast_data, type="income", amount=50000.0
            ),
            frequency="monthly",
            next_due_date=_forecast_due_date(),
            is_active=False,  # Inactive
            auto_confirm=False,
        )

        forecast = svc.calculate_forecast()

        # Should not include the inactive rule
        assert forecast.income_total == 0.0
        assert forecast.change == 0.0


# ---------------------------------------------------------------------------
# Negative balance warnings
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestNegativeBalanceWarning:
    def test_warning_when_balance_goes_negative(self, forecast_data):
        """Forecast flags when balance is projected to go negative."""
        svc = _svc(forecast_data["user_id"])

        # Large expense that exceeds balance
        RecurringRule.objects.create(
            user_id=forecast_data["user_id"],
            template_transaction=_make_template(
                forecast_data, type="expense", amount=25000.0, note="Big Purchase"
            ),
            frequency="monthly",
            next_due_date=_forecast_due_date(),
            is_active=True,
            auto_confirm=False,
        )

        forecast = svc.calculate_forecast()

        assert forecast.has_warning is True
        assert len(forecast.negative_days) > 0
        assert forecast.projected_balance < 0

    def test_no_warning_when_balance_stays_positive(self, forecast_data):
        """No warning when balance remains positive throughout."""
        svc = _svc(forecast_data["user_id"])

        # Small expense that doesn't exceed balance
        RecurringRule.objects.create(
            user_id=forecast_data["user_id"],
            template_transaction=_make_template(
                forecast_data, type="expense", amount=1000.0, note="Small Bill"
            ),
            frequency="monthly",
            next_due_date=_forecast_due_date(),
            is_active=True,
            auto_confirm=False,
        )

        forecast = svc.calculate_forecast()

        assert forecast.has_warning is False
        assert len(forecast.negative_days) == 0
        assert forecast.projected_balance > 0


# ---------------------------------------------------------------------------
# What-if scenarios (include/exclude rules)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestWhatIfScenarios:
    def test_include_rules_filter(self, forecast_data):
        """Include filter restricts forecast to specific rules."""
        svc = _svc(forecast_data["user_id"])

        # Create two income rules
        rule1 = RecurringRule.objects.create(
            user_id=forecast_data["user_id"],
            template_transaction=_make_template(
                forecast_data, type="income", amount=5000.0, note="Salary"
            ),
            frequency="monthly",
            next_due_date=_forecast_due_date(),
            is_active=True,
            auto_confirm=False,
        )

        RecurringRule.objects.create(
            user_id=forecast_data["user_id"],
            template_transaction=_make_template(
                forecast_data, type="income", amount=3000.0, note="Bonus"
            ),
            frequency="monthly",
            next_due_date=_forecast_due_date(2),
            is_active=True,
            auto_confirm=False,
        )

        # Include only rule1
        forecast = svc.calculate_forecast(include_rules=[str(rule1.id)])

        assert forecast.income_total == 5000.0
        assert forecast.change == 5000.0

    def test_exclude_rules_filter(self, forecast_data):
        """Exclude filter removes specific rules from forecast."""
        svc = _svc(forecast_data["user_id"])

        # Create two expense rules
        RecurringRule.objects.create(
            user_id=forecast_data["user_id"],
            template_transaction=_make_template(
                forecast_data, type="expense", amount=500.0, note="Netflix"
            ),
            frequency="monthly",
            next_due_date=_forecast_due_date(),
            is_active=True,
            auto_confirm=False,
        )

        rule2 = RecurringRule.objects.create(
            user_id=forecast_data["user_id"],
            template_transaction=_make_template(
                forecast_data, type="expense", amount=1000.0, note="Gym"
            ),
            frequency="monthly",
            next_due_date=_forecast_due_date(2),
            is_active=True,
            auto_confirm=False,
        )

        # Exclude rule2
        forecast = svc.calculate_forecast(exclude_rules=[str(rule2.id)])

        assert forecast.expense_total == 500.0
        assert forecast.change == -500.0


# ---------------------------------------------------------------------------
# Daily breakdown
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDailyBreakdown:
    def test_daily_events_populated(self, forecast_data):
        """Forecast days include events for rule occurrences."""
        svc = _svc(forecast_data["user_id"])

        due_date = _forecast_due_date()

        RecurringRule.objects.create(
            user_id=forecast_data["user_id"],
            template_transaction=_make_template(
                forecast_data, type="income", amount=1000.0, note="Payment"
            ),
            frequency="monthly",
            next_due_date=due_date,
            is_active=True,
            auto_confirm=False,
        )

        forecast = svc.calculate_forecast()

        # Find the day with the event
        event_day = next((d for d in forecast.days if d.date == due_date), None)

        assert event_day is not None
        assert len(event_day.events) == 1
        assert event_day.events[0]["type"] == "income"
        assert event_day.events[0]["amount"] == 1000.0

    def test_balance_steps_on_event_days(self, forecast_data):
        """Balance changes only on days with events."""
        svc = _svc(forecast_data["user_id"])

        due_date = date.today() + timedelta(days=5)

        RecurringRule.objects.create(
            user_id=forecast_data["user_id"],
            template_transaction=_make_template(
                forecast_data, type="expense", amount=500.0
            ),
            frequency="monthly",
            next_due_date=due_date,
            is_active=True,
            auto_confirm=False,
        )

        forecast = svc.calculate_forecast()

        # Balance should be constant until event day
        for day in forecast.days:
            if day.date < due_date:
                assert day.balance == forecast.current_balance
            elif day.date == due_date:
                assert day.balance == forecast.current_balance - 500.0
            else:
                assert day.balance == forecast.current_balance - 500.0


# ---------------------------------------------------------------------------
# get_forecast_summary
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestGetForecastSummary:
    def test_summary_dict_structure(self, forecast_data):
        """Summary returns all expected keys."""
        svc = _svc(forecast_data["user_id"])

        RecurringRule.objects.create(
            user_id=forecast_data["user_id"],
            template_transaction=_make_template(
                forecast_data, type="income", amount=2000.0
            ),
            frequency="monthly",
            next_due_date=_forecast_due_date(),
            is_active=True,
            auto_confirm=False,
        )

        summary = svc.get_forecast_summary()

        assert "current_balance" in summary
        assert "projected_balance" in summary
        assert "change" in summary
        assert "change_pct" in summary
        assert "has_warning" in summary
        assert "income_total" in summary
        assert "expense_total" in summary
        assert "currency" in summary
        assert "days_count" in summary
        assert "negative_days_count" in summary

        assert summary["current_balance"] == 20000.0
        assert summary["projected_balance"] == 22000.0
        assert summary["income_total"] == 2000.0

    def test_summary_change_percentage(self, forecast_data):
        """Summary includes correct change percentage."""
        svc = _svc(forecast_data["user_id"])

        RecurringRule.objects.create(
            user_id=forecast_data["user_id"],
            template_transaction=_make_template(
                forecast_data, type="income", amount=2000.0
            ),
            frequency="monthly",
            next_due_date=_forecast_due_date(),
            is_active=True,
            auto_confirm=False,
        )

        summary = svc.get_forecast_summary()

        # 2000 / 20000 * 100 = 10%
        assert abs(summary["change_pct"] - 10.0) < 0.1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestEdgeCases:
    def test_missing_account_raises(self, forecast_data):
        """Forecast with invalid account_id raises ValueError."""
        svc = _svc(forecast_data["user_id"])

        # Use a valid UUID format that doesn't exist in the database
        with pytest.raises(ValueError, match="not found"):
            svc.calculate_forecast(account_id="00000000-0000-0000-0000-000000000000")

    def test_dormant_accounts_excluded(self, forecast_data):
        """Dormant accounts are not included in forecast."""
        # Mark main account as dormant
        Account.objects.filter(id=forecast_data["main_account_id"]).update(
            is_dormant=True
        )

        svc = _svc(forecast_data["user_id"])
        forecast = svc.calculate_forecast()

        # Only savings account (5000) should be included
        assert forecast.current_balance == 5000.0

    def test_rules_without_amount_skipped(self, forecast_data):
        """Rules with missing or zero amount are skipped."""
        svc = _svc(forecast_data["user_id"])

        # Rule with zero amount
        RecurringRule.objects.create(
            user_id=forecast_data["user_id"],
            template_transaction=_make_template(
                forecast_data, amount=0.0, note="Zero amount"
            ),
            frequency="monthly",
            next_due_date=_forecast_due_date(),
            is_active=True,
            auto_confirm=False,
        )

        forecast = svc.calculate_forecast()

        assert forecast.income_total == 0.0
        assert forecast.expense_total == 0.0
