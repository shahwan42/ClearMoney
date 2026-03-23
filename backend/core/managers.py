"""
Custom managers for user-scoped data isolation.

Like Laravel's global scopes — every query automatically filters by user_id
when using Model.objects.for_user(uid). This replaces the repeated
``WHERE user_id = %s`` pattern across all raw SQL services.
"""

from django.db import models


class UserScopedQuerySet(models.QuerySet):
    """QuerySet that adds a ``for_user`` convenience filter."""

    def for_user(self, user_id: str) -> "UserScopedQuerySet":
        """Filter rows belonging to a specific user."""
        return self.filter(user_id=user_id)


class UserScopedManager(models.Manager):
    """Manager that exposes ``for_user`` at the top level.

    Usage::

        Account.objects.for_user(request.user_id).filter(is_dormant=False)
    """

    def get_queryset(self) -> UserScopedQuerySet:
        return UserScopedQuerySet(self.model, using=self._db)

    def for_user(self, user_id: str) -> UserScopedQuerySet:
        """Shortcut — equivalent to ``get_queryset().for_user(user_id)``."""
        return self.get_queryset().for_user(user_id)
