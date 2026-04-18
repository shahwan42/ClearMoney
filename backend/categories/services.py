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

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count, OuterRef, Subquery, Value
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Coalesce
from django.utils import timezone as django_tz
from django.utils.translation import get_language
from django.utils.translation import gettext as _

from categories.models import Category
from core.serializers import resolve_jsonb_name, serialize_instance, serialize_row
from transactions.models import Transaction

logger = logging.getLogger(__name__)

VALID_CATEGORY_TYPES = {"expense", "income"}

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
    out = serialize_instance(cat, _FIELDS)
    out["name"] = cat.get_display_name()
    return out


def _row_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    """Convert a .values() dict — stringify UUIDs, resolve name."""
    lang = (get_language() or "en").split("-")[0]
    return serialize_row(
        row,
        {
            "id": "id",
            "user_id": "user_id",
            "name": ("name", lambda v: resolve_jsonb_name(v, lang)),
            "type": "type",
            "icon": "icon",
            "is_system": "is_system",
            "is_archived": "is_archived",
            "display_order": "display_order",
            "created_at": "created_at",
            "updated_at": "updated_at",
        },
    )


def _annotate_name_en(qs: Any) -> Any:
    """Annotate queryset with name_en extracted from JSONB name->>'en'."""
    return qs.annotate(name_en=KeyTextTransform("en", "name"))


class CategoryService:
    """Like Laravel's CategoryService — validates input, guards system categories."""

    def __init__(self, user_id: str, tz: ZoneInfo) -> None:
        self.user_id = user_id
        self.tz = tz

    def _qs(self) -> Any:
        """Base queryset scoped to the current user."""
        return Category.objects.for_user(self.user_id)

    def get_all(self) -> list[dict[str, Any]]:
        """All non-archived categories, sorted by usage count then name."""
        rows = (
            _annotate_name_en(
                self._qs()
                .filter(is_archived=False)
                .annotate(usage_count=Coalesce(self._usage_subquery(), Value(0)))
            )
            .order_by("-usage_count", "name_en")
            .values(*_FIELDS)
        )
        return [_row_to_dict(row) for row in rows]

    def get_by_type(self, cat_type: str) -> list[dict[str, Any]]:
        """Non-archived categories filtered by type, sorted by usage then name."""
        rows = (
            _annotate_name_en(
                self._qs()
                .filter(type=cat_type, is_archived=False)
                .annotate(usage_count=Coalesce(self._usage_subquery(), Value(0)))
            )
            .order_by("-usage_count", "name_en")
            .values(*_FIELDS)
        )
        return [_row_to_dict(row) for row in rows]

    def get_by_id(self, cat_id: str) -> dict[str, Any] | None:
        """Single category by ID. Returns None if not found."""
        row = self._qs().filter(id=cat_id).values(*_FIELDS).first()
        if not row:
            return None
        return _row_to_dict(row)

    def _usage_subquery(self) -> Subquery:
        """Subquery counting this user's transactions per category.

        Scoped to self.user_id so ordering reflects the current user's habits only.
        Needed because Transaction.category has related_name='+' (no reverse).
        """
        return Subquery(
            Transaction.objects.filter(category_id=OuterRef("id"), user_id=self.user_id)
            .values("category_id")
            .annotate(cnt=Count("id"))
            .values("cnt")[:1]
        )

    def get_all_with_usage(self) -> list[dict[str, Any]]:
        """Active categories with transaction count, sorted by most used."""
        rows = (
            _annotate_name_en(
                self._qs()
                .filter(is_archived=False)
                .annotate(usage_count=Coalesce(self._usage_subquery(), Value(0)))
            )
            .order_by("-usage_count", "name_en")
            .values("id", "name", "icon", "is_system", "usage_count")
        )
        lang = (get_language() or "en").split("-")[0]
        return [
            {
                "id": str(r["id"]),
                "name": resolve_jsonb_name(r["name"], lang),
                "icon": r["icon"],
                "is_system": r["is_system"],
                "usage_count": r["usage_count"],
            }
            for r in rows
        ]

    def get_archived_with_usage(self) -> list[dict[str, Any]]:
        """Archived categories with transaction count."""
        rows = (
            _annotate_name_en(
                self._qs()
                .filter(is_archived=True)
                .annotate(usage_count=Coalesce(self._usage_subquery(), Value(0)))
            )
            .order_by("name_en")
            .values("id", "name", "icon", "is_system", "usage_count")
        )
        lang = (get_language() or "en").split("-")[0]
        return [
            {
                "id": str(r["id"]),
                "name": resolve_jsonb_name(r["name"], lang),
                "icon": r["icon"],
                "is_system": r["is_system"],
                "usage_count": r["usage_count"],
            }
            for r in rows
        ]

    def unarchive(self, cat_id: str) -> bool:
        """Restore an archived category."""
        updated = (
            self._qs()
            .filter(id=cat_id, is_archived=True)
            .update(is_archived=False, updated_at=django_tz.now())
        )
        if updated:
            logger.info("category.unarchived id=%s user=%s", cat_id, self.user_id)
        return bool(updated > 0)

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
            raise ValueError(_("category name is required"))

        if (
            _annotate_name_en(self._qs())
            .filter(name_en__iexact=name, is_archived=False)
            .exists()
        ):
            raise ValueError(_("A category with this name already exists"))

        cat = Category.objects.create(
            user_id=self.user_id,
            name=Category.make_name(en=name),
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
            raise ValueError(_("system categories cannot be modified"))

        name = name.strip() if name else ""
        if not name:
            raise ValueError(_("category name is required"))

        updated = (
            self._qs()
            .filter(id=cat_id)
            .update(
                name=Category.make_name(en=name),
                icon=icon,
                updated_at=django_tz.now(),
            )
        )
        if not updated:
            return None
        logger.info("category.updated id=%s user=%s", cat_id, self.user_id)
        return self.get_by_id(cat_id)

    def archive(self, cat_id: str) -> bool:
        """Soft-delete a category (sets is_archived=true). System categories cannot be archived.

        Like Laravel's SoftDeletes trait but with a boolean flag.

        Raises:
            ObjectDoesNotExist: If category not found.
            ValueError: If category is a system category.
        """
        existing = self.get_by_id(cat_id)
        if not existing:
            raise ObjectDoesNotExist(f"Category not found: {cat_id}")
        if existing["is_system"]:
            raise ValueError(_("system categories cannot be archived"))

        deleted = (
            self._qs()
            .filter(id=cat_id)
            .update(is_archived=True, updated_at=django_tz.now())
        )
        if deleted:
            logger.info("category.archived id=%s user=%s", cat_id, self.user_id)
        return bool(deleted > 0)
