"""
Category service layer — business logic for expense/income categories.

Like Laravel's CategoryService — validates input, guards system categories.
Categories are predefined labels for transactions (e.g., "Groceries", "Salary").
Some are "system" categories (seeded at setup, cannot be modified/deleted),
others are user-created.
"""

import logging
from typing import Any
from zoneinfo import ZoneInfo

from django.utils import timezone as django_tz

from core.models import Category

logger = logging.getLogger(__name__)

VALID_CATEGORY_TYPES = {"expense", "income"}

# Fields returned in category dicts
_FIELDS = (
    "id",
    "user_id",
    "name",
    "type",
    "icon",
    "is_system",
    "is_archived",
    "display_order",
    "created_at",
    "updated_at",
)


def _instance_to_dict(cat: Category) -> dict[str, Any]:
    """Convert a Category model instance to a dict."""
    return {
        "id": str(cat.id),
        "user_id": str(cat.user_id),
        "name": cat.name,
        "type": cat.type,
        "icon": cat.icon,
        "is_system": cat.is_system,
        "is_archived": cat.is_archived,
        "display_order": cat.display_order,
        "created_at": cat.created_at,
        "updated_at": cat.updated_at,
    }


def _row_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    """Convert a .values() dict — stringify UUIDs."""
    return {
        "id": str(row["id"]),
        "user_id": str(row["user_id"]),
        "name": row["name"],
        "type": row["type"],
        "icon": row["icon"],
        "is_system": row["is_system"],
        "is_archived": row["is_archived"],
        "display_order": row["display_order"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


class CategoryService:
    """Like Laravel's CategoryService — validates input, guards system categories."""

    def __init__(self, user_id: str, tz: ZoneInfo) -> None:
        self.user_id = user_id
        self.tz = tz

    def _qs(self) -> Any:
        """Base queryset scoped to the current user."""
        return Category.objects.for_user(self.user_id)

    def get_all(self) -> list[dict[str, Any]]:
        """All non-archived categories, ordered by display_order then name."""
        rows = (
            self._qs()
            .filter(is_archived=False)
            .order_by("display_order", "name")
            .values(*_FIELDS)
        )
        return [_row_to_dict(row) for row in rows]

    def get_by_type(self, cat_type: str) -> list[dict[str, Any]]:
        """Non-archived categories filtered by type ('expense' or 'income')."""
        rows = (
            self._qs()
            .filter(type=cat_type, is_archived=False)
            .order_by("display_order", "name")
            .values(*_FIELDS)
        )
        return [_row_to_dict(row) for row in rows]

    def get_by_id(self, cat_id: str) -> dict[str, Any] | None:
        """Single category by ID. Returns None if not found."""
        row = self._qs().filter(id=cat_id).values(*_FIELDS).first()
        if not row:
            return None
        return _row_to_dict(row)

    def create(
        self,
        name: str,
        cat_type: str = "expense",
        icon: str | None = None,
    ) -> dict[str, Any]:
        """Create a new custom category.

        Validates name (non-empty). Type is ignored — always stored as 'expense'
        since categories are type-agnostic (any category works with any tx type).
        """
        name = name.strip() if name else ""
        if not name:
            raise ValueError("category name is required")

        # Reject duplicate names (case-insensitive) for this user
        if self._qs().filter(name__iexact=name, is_archived=False).exists():
            raise ValueError("A category with this name already exists")

        cat = Category.objects.create(
            user_id=self.user_id,
            name=name,
            type="expense",
            icon=icon,
            is_system=False,
            display_order=0,
        )
        logger.info("category.created user=%s", self.user_id)
        return _instance_to_dict(cat)

    def update(
        self, cat_id: str, name: str, icon: str | None = None
    ) -> dict[str, Any] | None:
        """Update a custom category. System categories cannot be modified."""
        existing = self.get_by_id(cat_id)
        if not existing:
            return None
        if existing["is_system"]:
            raise ValueError("system categories cannot be modified")

        name = name.strip() if name else ""
        if not name:
            raise ValueError("category name is required")

        updated = (
            self._qs()
            .filter(id=cat_id)
            .update(name=name, icon=icon, updated_at=django_tz.now())
        )
        if not updated:
            return None
        logger.info("category.updated id=%s user=%s", cat_id, self.user_id)
        return self.get_by_id(cat_id)

    def archive(self, cat_id: str) -> bool:
        """Soft-delete a category (sets is_archived=true). System categories cannot be archived.

        Like Laravel's SoftDeletes trait but with a boolean flag.
        """
        existing = self.get_by_id(cat_id)
        if not existing:
            raise ValueError("category not found")
        if existing["is_system"]:
            raise ValueError("system categories cannot be archived")

        deleted = (
            self._qs()
            .filter(id=cat_id)
            .update(is_archived=True, updated_at=django_tz.now())
        )
        if deleted:
            logger.info("category.archived id=%s user=%s", cat_id, self.user_id)
        return bool(deleted > 0)
