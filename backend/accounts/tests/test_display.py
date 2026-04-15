"""Tests for accounts/display.py display helpers."""

from decimal import Decimal

from accounts.display import (
    cap_progress_percentage,
    get_balance_color_class,
    get_utilization_color_hex,
    get_your_money_color_class,
)


class TestGetBalanceColorClass:
    """Test get_balance_color_class helper."""

    def test_positive_balance_returns_teal(self) -> None:
        """Positive balance shows teal color."""
        result = get_balance_color_class(Decimal("1000.00"))
        assert result == "text-teal-700 dark:text-teal-400"

    def test_zero_balance_returns_teal(self) -> None:
        """Zero balance is non-negative, shows teal."""
        result = get_balance_color_class(Decimal("0.00"))
        assert result == "text-teal-700 dark:text-teal-400"

    def test_negative_balance_returns_red(self) -> None:
        """Negative balance (debt) shows red color."""
        result = get_balance_color_class(Decimal("-500.00"))
        assert result == "text-red-600"

    def test_small_negative_balance_returns_red(self) -> None:
        """Even small negative amounts show red."""
        result = get_balance_color_class(Decimal("-0.01"))
        assert result == "text-red-600"


class TestGetYourMoneyColorClass:
    """Test get_your_money_color_class helper."""

    def test_positive_your_money_returns_teal(self) -> None:
        """Positive 'your money' shows teal."""
        result = get_your_money_color_class(Decimal("5000.00"))
        assert result == "text-teal-600"

    def test_zero_your_money_returns_teal(self) -> None:
        """Zero 'your money' is non-negative, shows teal."""
        result = get_your_money_color_class(Decimal("0.00"))
        assert result == "text-teal-600"

    def test_negative_your_money_returns_red(self) -> None:
        """Negative 'your money' shows red (deficit)."""
        result = get_your_money_color_class(Decimal("-2000.00"))
        assert result == "text-red-600"


class TestGetUtilizationColorHex:
    """Test get_utilization_color_hex helper."""

    def test_high_utilization_returns_red(self) -> None:
        """Utilization > 80% returns red."""
        result = get_utilization_color_hex(85.0)
        assert result == "#ef4444"

    def test_exactly_80_percent_returns_amber(self) -> None:
        """Utilization exactly at 80% returns amber (not red)."""
        result = get_utilization_color_hex(80.0)
        assert result == "#f59e0b"

    def test_medium_utilization_returns_amber(self) -> None:
        """Utilization between 50% and 80% returns amber."""
        result = get_utilization_color_hex(65.0)
        assert result == "#f59e0b"

    def test_exactly_50_percent_returns_green(self) -> None:
        """Utilization exactly at 50% returns green."""
        result = get_utilization_color_hex(50.0)
        assert result == "#10b981"

    def test_low_utilization_returns_green(self) -> None:
        """Utilization <= 50% returns green."""
        result = get_utilization_color_hex(30.0)
        assert result == "#10b981"

    def test_zero_utilization_returns_green(self) -> None:
        """Zero utilization returns green."""
        result = get_utilization_color_hex(0.0)
        assert result == "#10b981"

    def test_very_high_utilization_returns_red(self) -> None:
        """Over-limit utilization (e.g., 150%) returns red."""
        result = get_utilization_color_hex(150.0)
        assert result == "#ef4444"


class TestCapProgressPercentage:
    """Test cap_progress_percentage helper."""

    def test_percentage_under_100_returns_unchanged(self) -> None:
        """Percentages under 100 are returned unchanged."""
        assert cap_progress_percentage(50.0) == 50.0
        assert cap_progress_percentage(99.9) == 99.9

    def test_exactly_100_returns_100(self) -> None:
        """Exactly 100% is returned unchanged."""
        assert cap_progress_percentage(100.0) == 100.0

    def test_percentage_over_100_is_capped(self) -> None:
        """Percentages over 100 are capped at 100."""
        assert cap_progress_percentage(120.0) == 100.0
        assert cap_progress_percentage(200.5) == 100.0

    def test_zero_percentage_returns_zero(self) -> None:
        """Zero percentage is returned unchanged."""
        assert cap_progress_percentage(0.0) == 0.0

    def test_negative_percentage_returned_unchanged(self) -> None:
        """Negative percentages are returned unchanged (edge case)."""
        assert cap_progress_percentage(-10.0) == -10.0
