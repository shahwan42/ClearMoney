"""
Cleanup service — deletes expired auth tokens and sessions.

Like Laravel's `php artisan auth:clear-resets` or Django's `clearsessions` command.

Called on startup and hourly via the django-cron service.
"""

import logging

from django.utils import timezone as django_tz

from core.models import AuthToken, Session

logger = logging.getLogger(__name__)


class CleanupService:
    """Removes expired auth tokens and sessions from the database.

    Both queries are simple DELETEs with a time comparison — no user_id
    needed since expiration is global.
    """

    def cleanup(self) -> tuple[int, int]:
        """Delete expired auth tokens and sessions.

        Returns:
            Tuple of (tokens_deleted, sessions_deleted).
        """
        now = django_tz.now()

        tokens_deleted, _ = AuthToken.objects.filter(expires_at__lt=now).delete()
        sessions_deleted, _ = Session.objects.filter(expires_at__lt=now).delete()

        if tokens_deleted > 0 or sessions_deleted > 0:
            logger.info(
                "cleanup.completed tokens=%d sessions=%d",
                tokens_deleted,
                sessions_deleted,
            )

        return tokens_deleted, sessions_deleted
