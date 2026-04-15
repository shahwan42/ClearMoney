"""Shared row/instance serialization helpers."""

import json
from collections.abc import Callable, Iterable
from decimal import Decimal
from typing import Any
from uuid import UUID


def serialize_value(val: Any) -> Any:
    """Convert UUID/Decimal to JSON-serializable types; pass-through everything else."""
    if val is None or isinstance(val, (bool, int, float, str)):
        return val
    if isinstance(val, UUID):
        return str(val)
    if isinstance(val, Decimal):
        return float(val)
    return val


def serialize_row(
    row: dict[str, Any],
    field_map: dict[str, tuple[str, Callable] | str],
) -> dict[str, Any]:
    """Convert a .values() dict to output dict.

    field_map: {output_key: 'source_key'} or {output_key: ('source_key', converter)}
    """
    out = {}
    for out_key, mapping in field_map.items():
        if isinstance(mapping, tuple):
            src_key, converter = mapping
            out[out_key] = converter(row[src_key])
        else:
            out[out_key] = serialize_value(row[mapping])
    return out


def serialize_instance(inst: Any, fields: Iterable[str]) -> dict[str, Any]:
    """Serialize a model instance to dict (UUID/Decimal auto-converted)."""
    return {f: serialize_value(getattr(inst, f)) for f in fields}


def parse_jsonb(value: Any) -> dict[str, Any] | None:
    """Parse a JSONB value that psycopg3 may return as a string in .values() results."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
    return None


def resolve_jsonb_name(name_value: Any, lang: str = "en") -> str:
    """Extract display string from a JSONB name dict like {"en": "...", "ar": "..."}."""
    if isinstance(name_value, str):
        return name_value
    if isinstance(name_value, dict):
        for key in (lang, "en"):
            if key in name_value:
                return str(name_value[key])
        if name_value:
            return str(next(iter(name_value.values())))
    return str(name_value) if name_value else ""
