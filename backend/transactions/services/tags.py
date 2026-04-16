"""Tag service — management of transaction tags."""

import logging
from typing import Any
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import Count

from transactions.models import Tag, Transaction

logger = logging.getLogger(__name__)


class TagService:
    """Service for managing transaction tags (CRUD, merge, rename)."""

    def __init__(self, user_id: str, tz: ZoneInfo) -> None:
        self.user_id = user_id
        self.tz = tz

    def get_all_with_usage(self) -> list[dict[str, Any]]:
        """Get all tags for the user with transaction counts."""
        tags = (
            Tag.objects.for_user(self.user_id)
            .annotate(count=Count("transactions"))
            .order_by("name")
        )
        return [
            {
                "id": str(t.id),
                "name": t.name,
                "color": t.color,
                "count": t.count,
            }
            for t in tags
        ]

    def create(self, name: str, color: str = "#64748b") -> Tag:
        """Create a new tag."""
        name = name.strip()
        if not name:
            raise ValueError("Tag name is required")

        tag, created = Tag.objects.get_or_create(
            user_id=self.user_id,
            name=name,
            defaults={"color": color}
        )
        return tag

    def update(self, tag_id: str, name: str = None, color: str = None) -> Tag:
        """Update a tag's name or color."""
        tag = Tag.objects.for_user(self.user_id).filter(id=tag_id).first()
        if not tag:
            raise ValueError("Tag not found")

        if name:
            name = name.strip()
            if name and name != tag.name:
                # Check if another tag with same name exists
                existing = Tag.objects.for_user(self.user_id).filter(name=name).exclude(id=tag_id).first()
                if existing:
                    raise ValueError(f"Tag with name '{name}' already exists")
                tag.name = name

        if color:
            tag.color = color

        tag.save()
        return tag

    def delete(self, tag_id: str) -> None:
        """Delete a tag (removes it from all transactions)."""
        Tag.objects.for_user(self.user_id).filter(id=tag_id).delete()

    def merge(self, source_id: str, target_id: str) -> None:
        """Merge source tag into target tag and delete source."""
        if source_id == target_id:
            return

        with transaction.atomic():
            source = Tag.objects.for_user(self.user_id).filter(id=source_id).first()
            target = Tag.objects.for_user(self.user_id).filter(id=target_id).first()

            if not source or not target:
                raise ValueError("Source or target tag not found")

            # Update all transactions that have the source tag
            txs = Transaction.objects.filter(tags=source)
            for tx in txs:
                tx.tags.remove(source)
                tx.tags.add(target)

            source.delete()
