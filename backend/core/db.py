"""Database utility helpers for raw SQL queries.

Reduces boilerplate in service files by providing cursor-to-dict mapping,
like Laravel's toArray() or Django ORM's .values().
"""

from typing import Any


def row_to_dict(cursor: Any, row: tuple[Any, ...]) -> dict[str, Any]:
    """Convert a database row to a dict using cursor column descriptions.

    Args:
        cursor: A database cursor with .description attribute
        row: A single row tuple from cursor.fetchone()

    Returns:
        Dict mapping column names to values
    """
    columns = [col.name for col in cursor.description]
    return dict(zip(columns, row, strict=True))


def rows_to_dicts(cursor: Any, rows: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
    """Convert multiple database rows to a list of dicts.

    Args:
        cursor: A database cursor with .description attribute
        rows: List of row tuples from cursor.fetchall()

    Returns:
        List of dicts mapping column names to values
    """
    columns = [col.name for col in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in rows]
