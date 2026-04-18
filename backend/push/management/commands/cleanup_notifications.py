"""
Management command: cleanup_notifications — delete notifications older than 30 days.

Removes all notification records (read and unread) older than 30 days to keep
the notifications table from growing unbounded.

Usage:
    python manage.py cleanup_notifications
"""

from datetime import timedelta
from typing import Any

from django.core.management.base import BaseCommand
from django.utils import timezone

from push.models import Notification


class Command(BaseCommand):
    help = "Delete notifications older than 30 days"

    def handle(self, *args: Any, **options: Any) -> None:
        cutoff = timezone.now() - timedelta(days=30)
        count, _ = Notification.objects.filter(created_at__lt=cutoff).delete()
        self.stdout.write(
            self.style.SUCCESS(f"Cleanup complete: {count} old notification(s) deleted")
        )
