"""Tests for transactions/display.py display helpers."""

from decimal import Decimal

from transactions.display import get_tx_amount_color_class, get_tx_indicator_color


class TestGetTxIndicatorColor:
    """Test get_tx_indicator_color helper."""

    def test_expense_returns_red(self) -> None:
        """Expense transactions show red indicator."""
        result = get_tx_indicator_color("expense")
        assert result == "#f87171"  # red-400

    def test_income_returns_green(self) -> None:
        """Income transactions show green indicator."""
        result = get_tx_indicator_color("income")
        assert result == "#4ade80"  # green-400

    def test_transfer_returns_blue(self) -> None:
        """Transfer transactions show blue indicator."""
        result = get_tx_indicator_color("transfer")
        assert result == "#60a5fa"  # blue-400

    def test_exchange_returns_blue(self) -> None:
        """Exchange transactions show blue indicator."""
        result = get_tx_indicator_color("exchange")
        assert result == "#60a5fa"  # blue-400

    def test_unknown_type_returns_blue(self) -> None:
        """Unknown transaction types default to blue."""
        result = get_tx_indicator_color("unknown")
        assert result == "#60a5fa"  # blue-400


class TestGetTxAmountColorClass:
    """Test get_tx_amount_color_class helper."""

    def test_expense_returns_red(self) -> None:
        """Expense amount always shows red."""
        result = get_tx_amount_color_class("expense")
        assert result == "text-red-600"

    def test_income_returns_green(self) -> None:
        """Income amount always shows green."""
        result = get_tx_amount_color_class("income")
        assert result == "text-green-600"

    def test_transfer_positive_delta_returns_blue(self) -> None:
        """Transfer with positive balance_delta shows blue."""
        result = get_tx_amount_color_class("transfer", Decimal("500.00"))
        assert result == "text-blue-600"

    def test_transfer_negative_delta_returns_red(self) -> None:
        """Transfer with negative balance_delta shows red."""
        result = get_tx_amount_color_class("transfer", Decimal("-500.00"))
        assert result == "text-red-600"

    def test_transfer_zero_delta_returns_blue(self) -> None:
        """Transfer with zero balance_delta returns blue (default)."""
        result = get_tx_amount_color_class("transfer", Decimal("0.00"))
        assert result == "text-blue-600"

    def test_transfer_no_delta_returns_blue(self) -> None:
        """Transfer without balance_delta defaults to blue."""
        result = get_tx_amount_color_class("transfer", None)
        assert result == "text-blue-600"

    def test_exchange_positive_delta_returns_blue(self) -> None:
        """Exchange with positive delta shows blue."""
        result = get_tx_amount_color_class("exchange", Decimal("1000.00"))
        assert result == "text-blue-600"

    def test_exchange_negative_delta_returns_red(self) -> None:
        """Exchange with negative delta shows red."""
        result = get_tx_amount_color_class("exchange", Decimal("-1000.00"))
        assert result == "text-red-600"

    def test_unknown_type_positive_delta_returns_blue(self) -> None:
        """Unknown type with positive delta returns blue."""
        result = get_tx_amount_color_class("unknown", Decimal("100.00"))
        assert result == "text-blue-600"

    def test_unknown_type_negative_delta_returns_red(self) -> None:
        """Unknown type with negative delta returns red."""
        result = get_tx_amount_color_class("unknown", Decimal("-100.00"))
        assert result == "text-red-600"
