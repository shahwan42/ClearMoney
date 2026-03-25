"""Database utility helpers for raw SQL queries.

Reduces boilerplate in service files by providing cursor-to-dict mapping,
like Laravel's toArray() or Django ORM's .values().
"""

from typing import Any


def row_to_dict(cursor: Any, row: tuple[Any, ...]) -> dict[str, Any]:
    """Convert a single database row tuple to a dict using cursor column metadata.

    Maps SQL column names to values, like Django's .values() or Laravel's toArray().
    The cursor.description attribute contains column metadata set after executing a query.

    Args:
        cursor: Database cursor (e.g., from django.db.connection.cursor())
                Must have .description attribute with column objects bearing a .name field
        row: Single row tuple from cursor.fetchone()

    Returns:
        Dictionary with column names as keys and row values as values

    Example:
        cursor.execute('SELECT id, email FROM users WHERE id = %s', [user_id])
        user_dict = row_to_dict(cursor, cursor.fetchone())
        # → {'id': UUID(...), 'email': 'user@example.com'}
    """
    columns = [col.name for col in cursor.description]
    return dict(zip(columns, row, strict=True))


def rows_to_dicts(cursor: Any, rows: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
    """Convert multiple database row tuples to a list of dicts.

    Batch version of row_to_dict for cursor.fetchall() results.
    Like Django's .values() or LaravelEloquent's ->toArray() for multiple rows.

    Args:
        cursor: Database cursor (e.g., from django.db.connection.cursor())
                Must have .description attribute with column objects bearing a .name field
        rows: List of row tuples from cursor.fetchall()

    Returns:
        List of dictionaries with column names as keys and row values as values

    Example:
        cursor.execute('SELECT id, email FROM users WHERE created_at > %s', [cutoff_date])
        users = rows_to_dicts(cursor, cursor.fetchall())
        # → [{'id': UUID(...), 'email': '...'}, ...]
    """
    columns = [col.name for col in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in rows]
