"""Tests for core.serializers helpers."""

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from core.serializers import (
    parse_jsonb,
    resolve_jsonb_name,
    serialize_instance,
    serialize_row,
    serialize_value,
)


class TestSerializeValue:
    def test_uuid_to_str(self) -> None:
        uid = uuid4()
        assert serialize_value(uid) == str(uid)

    def test_decimal_to_float(self) -> None:
        assert serialize_value(Decimal("123.45")) == 123.45

    def test_none_passthrough(self) -> None:
        assert serialize_value(None) is None

    def test_datetime_passthrough(self) -> None:
        dt = datetime(2024, 1, 15, 10, 30, 0)
        assert serialize_value(dt) == dt

    def test_date_passthrough(self) -> None:
        d = date(2024, 1, 15)
        assert serialize_value(d) == d

    def test_bool_passthrough(self) -> None:
        assert serialize_value(True) is True
        assert serialize_value(False) is False

    def test_int_passthrough(self) -> None:
        assert serialize_value(42) == 42

    def test_float_passthrough(self) -> None:
        assert serialize_value(3.14) == 3.14

    def test_str_passthrough(self) -> None:
        assert serialize_value("hello") == "hello"


class TestSerializeRow:
    def test_simple_field_map(self) -> None:
        row = {"id": uuid4(), "name": "Alice", "age": 30}
        result = serialize_row(row, {"id": "id", "name": "name", "age": "age"})
        assert result["id"] == str(row["id"])
        assert result["name"] == "Alice"
        assert result["age"] == 30

    def test_decimal_to_float_via_passthrough(self) -> None:
        row = {"amount": Decimal("99.99"), "name": "test"}
        result = serialize_row(row, {"amount": "amount", "name": "name"})
        assert result["amount"] == 99.99

    def test_with_converter_tuple(self) -> None:
        row = {"id": uuid4(), "data": "42"}
        result = serialize_row(
            row, {"id": "id", "data": ("data", lambda v: int(v) * 2)}
        )
        assert result["id"] == str(row["id"])
        assert result["data"] == 84

    def test_missing_key_raises(self) -> None:
        row = {"id": uuid4()}
        with pytest.raises(KeyError):
            serialize_row(row, {"id": "id", "name": "name"})

    def test_optional_uuid_field_with_none(self) -> None:
        row = {"id": uuid4(), "parent_id": None}
        result = serialize_row(row, {"id": "id", "parent_id": "parent_id"})
        assert result["parent_id"] is None

    def test_nested_dict_passthrough(self) -> None:
        nested = {"key": "value"}
        row = {"id": uuid4(), "data": nested}
        result = serialize_row(row, {"id": "id", "data": "data"})
        assert result["data"] == nested


class TestSerializeInstance:
    def test_basic(self) -> None:
        class FakeInstance:
            id = uuid4()
            name = "Alice"
            age = 30

        inst = FakeInstance()
        result = serialize_instance(inst, ["id", "name", "age"])
        assert result["id"] == str(inst.id)
        assert result["name"] == "Alice"
        assert result["age"] == 30

    def test_decimal_field_converted(self) -> None:
        class FakeInstance:
            id = uuid4()
            amount = Decimal("123.45")

        inst = FakeInstance()
        result = serialize_instance(inst, ["id", "amount"])
        assert result["amount"] == 123.45

    def test_optional_field_none(self) -> None:
        class FakeInstance:
            id = uuid4()
            note = None

        inst = FakeInstance()
        result = serialize_instance(inst, ["id", "note"])
        assert result["note"] is None


class TestResolveJsonbName:
    def test_dict_with_lang(self) -> None:
        name_value = {"en": "Groceries", "ar": "البقالة"}
        assert resolve_jsonb_name(name_value, "en") == "Groceries"
        assert resolve_jsonb_name(name_value, "ar") == "البقالة"

    def test_string_fallback(self) -> None:
        assert resolve_jsonb_name("Shopping", "en") == "Shopping"

    def test_en_fallback_when_lang_missing(self) -> None:
        name_value = {"en": "Salary", "fr": "Salaire"}
        assert resolve_jsonb_name(name_value, "de") == "Salary"

    def test_first_value_fallback(self) -> None:
        name_value = {"fr": "Salaire", "de": "Gehalt"}
        assert resolve_jsonb_name(name_value, "es") == "Salaire"

    def test_empty_fallback(self) -> None:
        assert resolve_jsonb_name({}, "en") == ""
        assert resolve_jsonb_name(None, "en") == ""

    def test_non_dict_non_str(self) -> None:
        assert resolve_jsonb_name(123, "en") == "123"


class TestParseJsonb:
    def test_dict_passthrough(self) -> None:
        data = {"key": "value"}
        assert parse_jsonb(data) == data

    def test_valid_json_string(self) -> None:
        assert parse_jsonb('{"key": "value"}') == {"key": "value"}

    def test_invalid_json_returns_none(self) -> None:
        assert parse_jsonb("not json") is None

    def test_empty_string_returns_none(self) -> None:
        assert parse_jsonb("") is None
        assert parse_jsonb("   ") is None

    def test_none_returns_none(self) -> None:
        assert parse_jsonb(None) is None

    def test_whitespace_json_string(self) -> None:
        assert parse_jsonb('  {"key": "value"}  ') == {"key": "value"}

    def test_non_dict_json_returns_none(self) -> None:
        assert parse_jsonb("[1, 2, 3]") is None
