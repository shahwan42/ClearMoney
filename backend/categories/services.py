"""
Category service layer — business logic for expense/income categories.

Port of Go's service/category.go + repository/category.go.

Like Laravel's CategoryService — validates input, guards system categories,
executes raw SQL. Categories are predefined labels for transactions
(e.g., "Groceries", "Salary"). Some are "system" categories (seeded at setup,
cannot be modified/deleted), others are user-created.
"""

import logging
from typing import Any
from zoneinfo import ZoneInfo

from django.db import connection

logger = logging.getLogger(__name__)

VALID_CATEGORY_TYPES = {"expense", "income"}

# Columns returned by category SELECT queries
_COLS = "id, user_id, name, type, icon, is_system, is_archived, display_order, created_at, updated_at"


def _row_to_dict(row: tuple[Any, ...]) -> dict[str, Any]:
    """Convert a category SQL row to a dict matching Go's JSON tags."""
    return {
        "id": str(row[0]),
        "user_id": str(row[1]),
        "name": row[2],
        "type": row[3],
        "icon": row[4],
        "is_system": row[5],
        "is_archived": row[6],
        "display_order": row[7],
        "created_at": row[8],
        "updated_at": row[9],
    }


class CategoryService:
    """Port of Go's CategoryService + CategoryRepo.

    Like Laravel's CategoryService — validates input, guards system categories.
    """

    def __init__(self, user_id: str, tz: ZoneInfo) -> None:
        self.user_id = user_id
        self.tz = tz

    def get_all(self) -> list[dict[str, Any]]:
        """All non-archived categories, ordered by type, display_order, name."""
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT {_COLS} FROM categories "
                "WHERE is_archived = false AND user_id = %s "
                "ORDER BY type, display_order, name",
                [self.user_id],
            )
            return [_row_to_dict(row) for row in cursor.fetchall()]

    def get_by_type(self, cat_type: str) -> list[dict[str, Any]]:
        """Non-archived categories filtered by type ('expense' or 'income')."""
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT {_COLS} FROM categories "
                "WHERE type = %s AND is_archived = false AND user_id = %s "
                "ORDER BY display_order, name",
                [cat_type, self.user_id],
            )
            return [_row_to_dict(row) for row in cursor.fetchall()]

    def get_by_id(self, cat_id: str) -> dict[str, Any] | None:
        """Single category by ID. Returns None if not found."""
        with connection.cursor() as cursor:
            cursor.execute(
                f"SELECT {_COLS} FROM categories WHERE id = %s AND user_id = %s",
                [cat_id, self.user_id],
            )
            row = cursor.fetchone()
            if not row:
                return None
            return _row_to_dict(row)

    def create(
        self, name: str, cat_type: str, icon: str | None = None
    ) -> dict[str, Any]:
        """Create a new custom category.

        Validates name (non-empty) and type (expense/income).
        System categories are only created by migrations, never via API.
        """
        name = name.strip() if name else ""
        if not name:
            raise ValueError("category name is required")
        if cat_type not in VALID_CATEGORY_TYPES:
            raise ValueError("category type must be 'expense' or 'income'")

        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO categories (user_id, name, type, icon, is_system, display_order) "
                "VALUES (%s, %s, %s, %s, false, 0) "
                "RETURNING id, is_system, is_archived, display_order, created_at, updated_at",
                [self.user_id, name, cat_type, icon],
            )
            row = cursor.fetchone()
            assert row is not None
            logger.info("category.created type=%s user=%s", cat_type, self.user_id)
            return {
                "id": str(row[0]),
                "user_id": self.user_id,
                "name": name,
                "type": cat_type,
                "icon": icon,
                "is_system": row[1],
                "is_archived": row[2],
                "display_order": row[3],
                "created_at": row[4],
                "updated_at": row[5],
            }

    def update(
        self, cat_id: str, name: str, icon: str | None = None
    ) -> dict[str, Any] | None:
        """Update a custom category. System categories cannot be modified.

        Port of Go's CategoryService.Update — fetch-then-check pattern.
        """
        existing = self.get_by_id(cat_id)
        if not existing:
            return None
        if existing["is_system"]:
            raise ValueError("system categories cannot be modified")

        name = name.strip() if name else ""
        if not name:
            raise ValueError("category name is required")

        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE categories SET name = %s, icon = %s, updated_at = now() "
                "WHERE id = %s AND user_id = %s "
                "RETURNING id, user_id, name, type, icon, is_system, is_archived, "
                "display_order, created_at, updated_at",
                [name, icon, cat_id, self.user_id],
            )
            row = cursor.fetchone()
            if not row:
                return None
            logger.info("category.updated id=%s user=%s", cat_id, self.user_id)
            return _row_to_dict(row)

    def archive(self, cat_id: str) -> bool:
        """Soft-delete a category. System categories cannot be archived.

        Port of Go's CategoryService.Archive — sets is_archived=true.
        Like Laravel's SoftDeletes trait but with a boolean flag.
        """
        existing = self.get_by_id(cat_id)
        if not existing:
            raise ValueError("category not found")
        if existing["is_system"]:
            raise ValueError("system categories cannot be archived")

        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE categories SET is_archived = true, updated_at = now() "
                "WHERE id = %s AND user_id = %s",
                [cat_id, self.user_id],
            )
            deleted: bool = cursor.rowcount > 0
            if deleted:
                logger.info("category.archived id=%s user=%s", cat_id, self.user_id)
            return deleted
