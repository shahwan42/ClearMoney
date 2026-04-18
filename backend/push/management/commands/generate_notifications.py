"""
Management command: generate_notifications — persist notification state for all users.

Iterates all users, calls NotificationService.generate_and_persist() per user.
Errors for individual users are caught and logged so one failing user doesn't
halt the entire job.

Usage:
    python manage.py generate_notifications
"""

import logging
import os
from typing import Any
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand

from auth_app.models import User
from push.services import NotificationService

logger = logging.getLogger(__name__)

_DEFAULT_TZ = os.environ.get("APP_TIMEZONE", "Africa/Cairo")


class Command(BaseCommand):
    help = "Generate and persist notifications for all users"

    def handle(self, *args: Any, **options: Any) -> None:
        users = User.objects.all()
        total_created = total_updated = total_resolved = 0
        tz = ZoneInfo(_DEFAULT_TZ)

        for user in users:
            try:
                svc = NotificationService(str(user.id), tz)
                stats = svc.generate_and_persist()
                total_created += stats["created"]
                total_updated += stats["updated"]
                total_resolved += stats["resolved"]
            except Exception:
                logger.exception(
                    "generate_notifications.failed_for_user user_id=%s", user.id
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {total_created} created, {total_updated} updated, "
                f"{total_resolved} resolved across {users.count()} user(s)"
            )
        )
