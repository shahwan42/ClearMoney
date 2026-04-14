"""Tests for untested template tags and filters in core/templatetags/money.py."""

import datetime
from decimal import Decimal
from typing import Any

from core.templatetags.money import (
    abs_float,
    add_float,
    bar_style,
    chart_color,
    conic_gradient,
    deref,
    deref_float,
    format_account_type,
    format_date_short,
    format_num,
    format_type,
    get_item,
    institution_display_name,
    is_image_icon,
    make_dict,
    sparkline_points,
)


class TestFormatNum:
    def test_positive(self) -> None:
        assert format_num(1234.56) == "1,234.56"

    def test_zero(self) -> None:
        assert format_num(0) == "0.00"

    def test_decimal(self) -> None:
        assert format_num(Decimal("9999.99")) == "9,999.99"


class TestFormatDateShort:
    def test_basic(self) -> None:
        d = datetime.date(2026, 3, 2)
        assert format_date_short(d) == "Mar 2"

    def test_non_date_returns_str(self) -> None:
        assert format_date_short("not a date") == "not a date"


class TestFormatAccountType:
    def test_savings(self) -> None:
        assert format_account_type("savings") == "Savings"

    def test_credit_card(self) -> None:
        assert format_account_type("credit_card") == "Credit Card"

    def test_credit_limit(self) -> None:
        assert format_account_type("credit_limit") == "Credit Limit"

    def test_current(self) -> None:
        assert format_account_type("current") == "Current"

    def test_cash(self) -> None:
        assert format_account_type("cash") == "Cash"

    def test_unknown_passthrough(self) -> None:
        assert format_account_type("unknown_type") == "unknown_type"


class TestFormatType:
    def test_expense(self) -> None:
        assert format_type("expense") == "Expense"

    def test_loan_out(self) -> None:
        assert format_type("loan_out") == "Loan Given"

    def test_loan_in(self) -> None:
        assert format_type("loan_in") == "Loan Received"

    def test_loan_repayment(self) -> None:
        assert format_type("loan_repayment") == "Loan Repayment"

    def test_transfer(self) -> None:
        assert format_type("transfer") == "Transfer"

    def test_unknown_passthrough(self) -> None:
        assert format_type("custom") == "custom"


class TestDeref:
    def test_none(self) -> None:
        assert deref(None) == ""

    def test_string(self) -> None:
        assert deref("hello") == "hello"

    def test_number(self) -> None:
        assert deref(42) == "42"


class TestDerefFloat:
    def test_none(self) -> None:
        assert deref_float(None) == 0.0

    def test_decimal(self) -> None:
        assert deref_float(Decimal("42.5")) == 42.5

    def test_int(self) -> None:
        assert deref_float(100) == 100.0


class TestAddFloat:
    def test_basic(self) -> None:
        assert add_float(10.5, 20.3) == 30.8

    def test_decimals(self) -> None:
        assert add_float(Decimal("10"), Decimal("5")) == 15.0


class TestAbsFloat:
    def test_negative(self) -> None:
        assert abs_float(-42.5) == 42.5

    def test_positive(self) -> None:
        assert abs_float(42.5) == 42.5

    def test_zero(self) -> None:
        assert abs_float(0) == 0.0


class TestGetItem:
    def test_existing_key(self) -> None:
        d: dict[str, Any] = {"name": "Ahmed"}
        assert get_item(d, "name") == "Ahmed"

    def test_missing_key(self) -> None:
        d: dict[str, Any] = {"name": "Ahmed"}
        assert get_item(d, "age") is None

    def test_non_dict_returns_none(self) -> None:
        assert get_item("not a dict", "key") is None


class TestSparklinePoints:
    def test_basic_values(self) -> None:
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        result = sparkline_points(values)
        assert isinstance(result, str)
        # Should have 5 points (comma-separated x,y pairs)
        points = result.split(" ")
        assert len(points) == 5

    def test_single_value(self) -> None:
        result = sparkline_points([100.0])
        assert result == "0,20 100,20"

    def test_empty_list(self) -> None:
        result = sparkline_points([])
        assert result == ""

    def test_all_same_values(self) -> None:
        """When all values are equal, should not divide by zero."""
        result = sparkline_points([50.0, 50.0, 50.0])
        assert isinstance(result, str)
        assert len(result) > 0


class TestBarStyle:
    def test_basic(self) -> None:
        result = bar_style(50.0, "#0d9488")
        assert "height:50.0%" in result
        assert "#0d9488" in result

    def test_zero_height(self) -> None:
        result = bar_style(0.0, "#0d9488")
        assert "height:0.0%" in result

    def test_full_height(self) -> None:
        result = bar_style(100.0, "#dc2626")
        assert "height:100.0%" in result


class TestMakeDict:
    def test_creates_dict(self) -> None:
        result = make_dict(color="#0d9488", values=[1, 2, 3])
        assert result == {"color": "#0d9488", "values": [1, 2, 3]}

    def test_empty(self) -> None:
        result = make_dict()
        assert result == {}


# ---------------------------------------------------------------------------
# is_image_icon and institution_display_name tests
# ---------------------------------------------------------------------------


class TestIsImageIcon:
    """is_image_icon returns True for image filenames, False for emoji/other."""

    def test_png_returns_true(self) -> None:
        assert is_image_icon("bank-logo.png") is True

    def test_svg_returns_true(self) -> None:
        assert is_image_icon("icon.svg") is True

    def test_emoji_returns_false(self) -> None:
        assert is_image_icon("\U0001f3e6") is False


class TestInstitutionDisplayName:
    """institution_display_name expands preset abbreviations to full names."""

    def test_preset_abbreviation(self) -> None:
        # "CIB" is stored in the DB; display name should be the full preset name
        result = institution_display_name("CIB")
        assert result == "CIB - Commercial International Bank"

    def test_custom_name_returns_as_is(self) -> None:
        result = institution_display_name("My Custom Bank")
        assert result == "My Custom Bank"


class TestChartColor:
    """chart_color returns CSS custom-property references for dark mode support."""

    def test_index_zero_returns_var(self) -> None:
        assert chart_color(0) == "var(--chart-1)"

    def test_index_one_returns_var(self) -> None:
        assert chart_color(1) == "var(--chart-2)"

    def test_index_seven_returns_var(self) -> None:
        assert chart_color(7) == "var(--chart-8)"

    def test_wraps_at_eight(self) -> None:
        # Palette has 8 entries; index 8 wraps back to --chart-1
        assert chart_color(8) == "var(--chart-1)"

    def test_no_raw_hex(self) -> None:
        # Should not return raw hex — dark mode relies on CSS variables
        result = chart_color(0)
        assert not result.startswith("#"), (
            "chart_color must return a CSS var, not a hex value"
        )


class TestConicGradient:
    """conic_gradient uses CSS custom properties for dark-mode-compatible colors."""

    def test_empty_uses_css_var(self) -> None:
        # Empty segments should use --chart-empty var, not a hardcoded hex
        result = conic_gradient([])
        assert "var(--chart-empty)" in result

    def test_segments_use_css_vars(self) -> None:
        segments = [
            {"color": "var(--chart-1)", "percentage": 60.0},
            {"color": "var(--chart-2)", "percentage": 40.0},
        ]
        result = conic_gradient(segments)
        assert "var(--chart-1)" in result
        assert "var(--chart-2)" in result

    def test_partial_fill_uses_css_var(self) -> None:
        # When segments don't fill 100%, remainder uses --chart-empty
        segments = [{"color": "var(--chart-1)", "percentage": 50.0}]
        result = conic_gradient(segments)
        assert "var(--chart-empty)" in result
