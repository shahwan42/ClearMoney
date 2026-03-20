"""Tests for credit card billing cycle calculations in core/billing.py."""

import datetime

from core.billing import (
    BillingCycleInfo,
    compute_due_date,
    get_billing_cycle_info,
    get_credit_card_utilization,
    interest_free_remaining,
    parse_billing_cycle,
)


class TestParseBillingCycle:
    """parse_billing_cycle reads statement_day/due_day from metadata dict."""

    def test_valid_metadata(self) -> None:
        metadata = {"statement_day": 25, "due_day": 10}
        assert parse_billing_cycle(metadata) == (25, 10)

    def test_none_metadata(self) -> None:
        assert parse_billing_cycle(None) is None

    def test_empty_dict(self) -> None:
        assert parse_billing_cycle({}) is None

    def test_missing_statement_day(self) -> None:
        assert parse_billing_cycle({"due_day": 10}) is None

    def test_missing_due_day(self) -> None:
        assert parse_billing_cycle({"statement_day": 25}) is None

    def test_zero_statement_day(self) -> None:
        assert parse_billing_cycle({"statement_day": 0, "due_day": 10}) is None

    def test_zero_due_day(self) -> None:
        assert parse_billing_cycle({"statement_day": 25, "due_day": 0}) is None

    def test_string_metadata_raises(self) -> None:
        """Non-dict metadata raises AttributeError (caller should validate)."""
        import pytest

        with pytest.raises(AttributeError):
            parse_billing_cycle("not a dict")  # type: ignore[arg-type]


class TestComputeDueDate:
    """compute_due_date calculates the next CC payment due date."""

    def test_due_day_after_statement_day_same_month(self) -> None:
        # statement=1, due=15 — due is in the same month as period end
        today = datetime.date(2026, 3, 1)
        result = compute_due_date(1, 15, today)
        assert result == datetime.date(2026, 3, 15)

    def test_due_day_before_statement_day_next_month(self) -> None:
        # statement=25, due=10: today>25 → period_end_month=Apr, due<statement → May 10
        today = datetime.date(2026, 3, 26)
        result = compute_due_date(25, 10, today)
        assert result == datetime.date(2026, 5, 10)

    def test_year_boundary(self) -> None:
        # statement=25, due=10: today=Dec 26>25 → period_end_month=Jan 2027, due→Feb 10
        today = datetime.date(2026, 12, 26)
        result = compute_due_date(25, 10, today)
        assert result == datetime.date(2027, 2, 10)

    def test_before_statement_day(self) -> None:
        today = datetime.date(2026, 3, 20)
        result = compute_due_date(25, 10, today)
        assert isinstance(result, datetime.date)

    def test_on_statement_day(self) -> None:
        today = datetime.date(2026, 3, 25)
        result = compute_due_date(25, 10, today)
        assert isinstance(result, datetime.date)


class TestGetBillingCycleInfo:
    """get_billing_cycle_info returns a full BillingCycleInfo dataclass."""

    def test_returns_billing_cycle_info(self) -> None:
        today = datetime.date(2026, 3, 15)
        info = get_billing_cycle_info(25, 10, today)
        assert isinstance(info, BillingCycleInfo)
        assert info.statement_day == 25
        assert info.due_day == 10

    def test_period_start_before_period_end(self) -> None:
        today = datetime.date(2026, 3, 15)
        info = get_billing_cycle_info(25, 10, today)
        assert info.period_start < info.period_end

    def test_days_until_due_non_negative_near_due(self) -> None:
        today = datetime.date(2026, 3, 7)
        info = get_billing_cycle_info(25, 10, today)
        assert info.days_until_due >= 0

    def test_is_due_soon_within_7_days(self) -> None:
        # statement=1, due=8: today=Apr 3 (>1) → period_end=May 1, due=May 8
        # days_until_due = 35 — still far. Need today near due.
        # statement=1, due=8: today=Apr 1 (<=1) → period_end=Apr 1, due=Apr 8
        # days_until_due = 7
        today = datetime.date(2026, 4, 1)
        info = get_billing_cycle_info(1, 8, today)
        assert info.days_until_due == 7
        assert info.is_due_soon is True

    def test_not_due_soon_when_far(self) -> None:
        today = datetime.date(2026, 3, 1)
        info = get_billing_cycle_info(25, 10, today)
        assert info.days_until_due > 7
        assert info.is_due_soon is False

    def test_year_boundary(self) -> None:
        today = datetime.date(2026, 12, 28)
        info = get_billing_cycle_info(25, 10, today)
        assert info.period_end.year == 2027 or info.due_date.year == 2027


class TestGetCreditCardUtilization:
    """get_credit_card_utilization returns 0-100 percentage."""

    def test_zero_balance(self) -> None:
        assert get_credit_card_utilization(0.0, 10000.0) == 0.0

    def test_half_utilized(self) -> None:
        assert get_credit_card_utilization(-5000.0, 10000.0) == 50.0

    def test_fully_utilized(self) -> None:
        assert get_credit_card_utilization(-10000.0, 10000.0) == 100.0

    def test_zero_limit_returns_zero(self) -> None:
        assert get_credit_card_utilization(-5000.0, 0.0) == 0.0

    def test_none_limit_returns_zero(self) -> None:
        assert get_credit_card_utilization(-5000.0, None) == 0.0

    def test_positive_balance_returns_zero(self) -> None:
        """Positive balance (overpayment) should return 0, not negative."""
        assert get_credit_card_utilization(500.0, 10000.0) == 0.0


class TestInterestFreeRemaining:
    """interest_free_remaining returns (days_remaining, is_urgent)."""

    def test_plenty_of_time(self) -> None:
        period_end = datetime.date(2026, 3, 25)
        today = datetime.date(2026, 3, 1)
        days, is_urgent = interest_free_remaining(period_end, today)
        assert days > 7
        assert is_urgent is False

    def test_urgent_when_few_days_left(self) -> None:
        # interest_free_end = period_end + 55 days
        period_end = datetime.date(2026, 3, 1)
        # 55 days from Mar 1 = Apr 25
        today = datetime.date(2026, 4, 20)
        days, is_urgent = interest_free_remaining(period_end, today)
        assert 0 < days <= 7
        assert is_urgent is True

    def test_past_period_returns_zero(self) -> None:
        period_end = datetime.date(2026, 1, 1)
        today = datetime.date(2026, 6, 1)
        days, is_urgent = interest_free_remaining(period_end, today)
        assert days == 0

    def test_custom_total_days(self) -> None:
        period_end = datetime.date(2026, 3, 1)
        today = datetime.date(2026, 3, 1)
        days, _ = interest_free_remaining(period_end, today, total_days=30)
        assert days == 30
