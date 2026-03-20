"""
Management command: take_snapshots — daily balance snapshot + backfill.

For each user:
1. Captures today's net worth and per-account balances
2. Backfills missing days (default: 90 days)

Safe to run multiple times — UPSERT semantics prevent duplicates.

Usage:
    python manage.py take_snapshots              # Default 90-day backfill
    python manage.py take_snapshots --days 7     # 7-day backfill only
"""

from argparse import ArgumentParser
from typing import Any
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.management.base import BaseCommand

from jobs.services.snapshot import SnapshotService


class Command(BaseCommand):
    help = "Take daily balance snapshots for all users + backfill missing days"

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--days",
            type=int,
            default=90,
            help="Number of days to backfill (default: 90)",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        days: int = options.get("days", 90)
        tz = ZoneInfo(settings.TIME_ZONE)
        svc = SnapshotService(tz)

        backfilled = svc.take_all_user_snapshots(days=days)
        self.stdout.write(
            self.style.SUCCESS(f"Snapshots complete: {backfilled} day(s) backfilled")
        )
