"""Shared parsing utilities used across views and services."""

from typing import Any


def parse_float_or_none(value: Any) -> float | None:
    """Parse a value to float, returning None if empty or invalid.

    Handles str, int, float, None, and whitespace-only strings.
    """
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def parse_float_or_zero(value: Any) -> float:
    """Parse a value to float, returning 0.0 if empty or invalid."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0
