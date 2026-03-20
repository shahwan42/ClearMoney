"""Tests for core.utils parsing helpers."""

from core.utils import parse_float_or_none, parse_float_or_zero


class TestParseFloatOrNone:
    """Tests for parse_float_or_none()."""

    def test_valid_float_string(self) -> None:
        assert parse_float_or_none("3.14") == 3.14

    def test_valid_integer_string(self) -> None:
        assert parse_float_or_none("42") == 42.0

    def test_negative_value(self) -> None:
        assert parse_float_or_none("-10.5") == -10.5

    def test_zero(self) -> None:
        assert parse_float_or_none("0") == 0.0

    def test_none_returns_none(self) -> None:
        assert parse_float_or_none(None) is None

    def test_empty_string_returns_none(self) -> None:
        assert parse_float_or_none("") is None

    def test_whitespace_only_returns_none(self) -> None:
        assert parse_float_or_none("   ") is None

    def test_invalid_string_returns_none(self) -> None:
        assert parse_float_or_none("abc") is None

    def test_float_passthrough(self) -> None:
        assert parse_float_or_none(3.14) == 3.14

    def test_int_passthrough(self) -> None:
        assert parse_float_or_none(42) == 42.0


class TestParseFloatOrZero:
    """Tests for parse_float_or_zero()."""

    def test_valid_float_string(self) -> None:
        assert parse_float_or_zero("3.14") == 3.14

    def test_valid_integer_string(self) -> None:
        assert parse_float_or_zero("42") == 42.0

    def test_negative_value(self) -> None:
        assert parse_float_or_zero("-10.5") == -10.5

    def test_zero(self) -> None:
        assert parse_float_or_zero("0") == 0.0

    def test_none_returns_zero(self) -> None:
        assert parse_float_or_zero(None) == 0.0

    def test_empty_string_returns_zero(self) -> None:
        assert parse_float_or_zero("") == 0.0

    def test_invalid_string_returns_zero(self) -> None:
        assert parse_float_or_zero("abc") == 0.0

    def test_float_passthrough(self) -> None:
        assert parse_float_or_zero(3.14) == 3.14
