"""
Management command: cleanup_sessions — delete expired auth tokens and sessions.

Like Django's built-in `clearsessions` but for the custom auth/session tables.

Usage:
    python manage.py cleanup_sessions
"""

from typing import Any

from django.core.management.base import BaseCommand

from jobs.services.cleanup import CleanupService


class Command(BaseCommand):
    help = "Delete expired auth tokens and sessions"

    def handle(self, *args: Any, **options: Any) -> None:
        svc = CleanupService()
        tokens, sessions = svc.cleanup()
        self.stdout.write(
            self.style.SUCCESS(
                f"Cleanup complete: {tokens} expired token(s), "
                f"{sessions} expired session(s) removed"
            )
        )
