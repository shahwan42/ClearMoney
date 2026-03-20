"""Dashboard helpers — shared utility functions for dashboard sub-modules."""

import json
from typing import Any


def _parse_jsonb(value: Any) -> dict[str, Any] | None:
    """Parse a JSONB value that psycopg3 may return as a string.

    psycopg3 returns JSONB columns as strings, not dicts.
    This helper handles both cases safely.
    """
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
