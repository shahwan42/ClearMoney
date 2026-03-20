"""Tests for core.utils parsing helpers."""

from django.test import RequestFactory

from core.utils import parse_float_or_none, parse_float_or_zero, parse_json_body


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


class TestParseJsonBody:
    """Tests for parse_json_body()."""

    def _make_request(self, body: bytes) -> object:
        rf = RequestFactory()
        request = rf.post("/test", data=body, content_type="application/json")
        return request

    def test_valid_json(self) -> None:
        request = self._make_request(b'{"key": "value"}')
        result = parse_json_body(request)  # type: ignore[arg-type]
        assert result == {"key": "value"}

    def test_invalid_json_returns_none(self) -> None:
        request = self._make_request(b"not json")
        assert parse_json_body(request) is None  # type: ignore[arg-type]

    def test_empty_body_returns_none(self) -> None:
        request = self._make_request(b"")
        assert parse_json_body(request) is None  # type: ignore[arg-type]

    def test_json_array_returns_none(self) -> None:
        request = self._make_request(b"[1, 2, 3]")
        assert parse_json_body(request) is None  # type: ignore[arg-type]

    def test_nested_json(self) -> None:
        request = self._make_request(b'{"a": {"b": 1}}')
        result = parse_json_body(request)  # type: ignore[arg-type]
        assert result == {"a": {"b": 1}}
