"""
Tests for core/billing.py — billing cycle date math and utilization.

Pure function tests — no database required.
"""

from datetime import date

import pytest

from core.billing import (
    compute_due_date,
    get_billing_cycle_info,
    get_credit_card_utilization,
    interest_free_remaining,
    parse_billing_cycle,
)


class TestParseBillingCycle:
    def test_valid_metadata(self):
        result = parse_billing_cycle({"statement_day": 15, "due_day": 5})
        assert result == (15, 5)

    def test_empty_metadata(self):
        assert parse_billing_cycle({}) is None

    def test_none_metadata(self):
        assert parse_billing_cycle(None) is None

    def test_zero_values(self):
        assert parse_billing_cycle({"statement_day": 0, "due_day": 5}) is None

    def test_missing_keys(self):
        assert parse_billing_cycle({"statement_day": 15}) is None


class TestComputeDueDate:
    def test_before_statement_day(self):
        # Today is Mar 10, statement=15, due=5 → due Apr 5
        result = compute_due_date(15, 5, date(2026, 3, 10))
        assert result == date(2026, 4, 5)

    def test_after_statement_day(self):
        # Today is Mar 20, statement=15, due=5 → due May 5
        result = compute_due_date(15, 5, date(2026, 3, 20))
        assert result == date(2026, 5, 5)

    def test_due_day_after_statement_day(self):
        # statement=5, due=25 → due same month as period end
        result = compute_due_date(5, 25, date(2026, 3, 3))
        assert result == date(2026, 3, 25)


class TestGetBillingCycleInfo:
    def test_before_statement_day(self):
        info = get_billing_cycle_info(15, 5, date(2026, 3, 10))
        assert info.period_start == date(2026, 2, 16)
        assert info.period_end == date(2026, 3, 15)
        assert info.due_date == date(2026, 4, 5)
        assert info.days_until_due == 26
        assert info.is_due_soon is False

    def test_after_statement_day(self):
        info = get_billing_cycle_info(15, 5, date(2026, 3, 20))
        assert info.period_start == date(2026, 3, 16)
        assert info.period_end == date(2026, 4, 15)
        assert info.due_date == date(2026, 5, 5)
        assert info.days_until_due == 46

    def test_due_soon(self):
        # Mar 10: before statement day 15 → period Feb 16 - Mar 15, due Apr 5
        # days_until_due = (Apr 5 - Mar 10).days = 26 → NOT due soon
        # Use Apr 1: before statement day 15 → period Mar 16 - Apr 15, due May 5
        # days_until_due = (May 5 - Apr 1).days = 34 → NOT due soon
        # Use May 1: before statement day 15 → period Apr 16 - May 15, due Jun 5
        # days_until_due = (Jun 5 - May 1).days = 35 → NOT due soon
        # Need to find a date where due_date - today <= 7
        # Use May 2 with statement_day=5, due_day=8:
        # May 2 before statement 5 → period Apr 6 - May 5, due May 8
        # days_until_due = (May 8 - May 2).days = 6 → IS due soon!
        info = get_billing_cycle_info(5, 8, date(2026, 5, 2))
        assert info.due_date == date(2026, 5, 8)
        assert info.days_until_due == 6
        assert info.is_due_soon is True


class TestGetCreditCardUtilization:
    def test_zero_balance(self):
        assert get_credit_card_utilization(0.0, 500000.0) == 0.0

    def test_positive_balance(self):
        # balance is positive means no debt
        assert get_credit_card_utilization(1000.0, 500000.0) == 0.0

    def test_normal_usage(self):
        # balance = -120000, limit = 500000 → 24%
        result = get_credit_card_utilization(-120000.0, 500000.0)
        assert result == pytest.approx(24.0)

    def test_no_limit(self):
        assert get_credit_card_utilization(-120000.0, None) == 0.0

    def test_zero_limit(self):
        assert get_credit_card_utilization(-120000.0, 0.0) == 0.0


class TestInterestFreeRemaining:
    def test_remaining_days(self):
        remaining, urgent = interest_free_remaining(
            date(2026, 3, 15), date(2026, 3, 20)
        )
        assert remaining == 50  # 55 - 5
        assert urgent is False

    def test_expired(self):
        remaining, urgent = interest_free_remaining(date(2026, 1, 1), date(2026, 3, 20))
        assert remaining == 0
        assert urgent is False

    def test_urgent(self):
        # period_end=Mar 15, +55 days = May 9. today=May 4. remaining=5
        remaining, urgent = interest_free_remaining(date(2026, 3, 15), date(2026, 5, 4))
        assert remaining == 5
        assert urgent is True
