"""Push notification models — persistent notification state for the notification center."""

import uuid

from django.db import models
from django.db.models import Func
from django.db.models.functions import Now

from core.managers import UserScopedManager

GEN_UUID = Func(function="gen_random_uuid")


class Notification(models.Model):
    """Persisted notification with read/unread tracking.

    Tags are used for deduplication — one notification per (user, tag).
    The pipeline upserts by tag so recurring conditions don't stack.
    """

    objects = UserScopedManager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, db_default=GEN_UUID)
    user = models.ForeignKey(
        "auth_app.User", on_delete=models.CASCADE, db_column="user_id", db_index=True
    )
    title = models.CharField(max_length=255)
    body = models.TextField()
    url = models.CharField(max_length=500, blank=True, default="")
    tag = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False, db_default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())
    updated_at = models.DateTimeField(auto_now=True, db_default=Now())

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "tag"],
                name="notifications_user_tag_unique",
            ),
        ]
        indexes = [
            models.Index(
                fields=["user", "is_read", "-created_at"],
                name="notif_user_read_created_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({'read' if self.is_read else 'unread'})"
