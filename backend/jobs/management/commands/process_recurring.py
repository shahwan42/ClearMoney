"""
Management command: process_recurring — auto-create due recurring transactions.

Wraps the existing RecurringService.process_due_rules() for each user.
No new service needed — reuses backend/recurring/services.py.

Iterates all users and calls RecurringService.process_due_rules() for each.

Usage:
    python manage.py process_recurring
"""

from typing import Any
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.management.base import BaseCommand

from auth_app.models import User
from recurring.services import RecurringService


class Command(BaseCommand):
    help = "Process due recurring rules (auto_confirm=true) for all users"

    def handle(self, *args: Any, **options: Any) -> None:
        tz = ZoneInfo(settings.TIME_ZONE)
        user_ids = self._get_all_user_ids()
        total_created = 0

        for user_id in user_ids:
            svc = RecurringService(user_id, tz)
            count = svc.process_due_rules()
            if count > 0:
                self.stdout.write(f"User {user_id}: created {count} transaction(s)")
                total_created += count

        self.stdout.write(
            self.style.SUCCESS(
                f"Recurring processing complete: {total_created} transaction(s) created"
            )
        )

    def _get_all_user_ids(self) -> list[str]:
        """Get all user IDs from the users table."""
        return [str(uid) for uid in User.objects.values_list("id", flat=True)]
