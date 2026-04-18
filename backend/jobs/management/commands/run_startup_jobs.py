"""
Management command: run_startup_jobs — orchestrate all background jobs.

Runs all 5 jobs in the standard startup sequence:
1. cleanup_sessions (remove expired tokens/sessions)
2. process_recurring (auto-create due transactions)
3. reconcile_balances (report-only, no auto-fix)
4. refresh_views (refresh materialized views)
5. take_snapshots (daily snapshot + 90-day backfill)

Usage:
    python manage.py run_startup_jobs
"""

import logging
from typing import Any

from django.core.management import call_command
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run all startup background jobs in sequence"

    def handle(self, *args: Any, **options: Any) -> None:
        jobs: list[tuple[str, dict[str, Any]]] = [
            ("cleanup_sessions", {}),
            ("process_recurring", {}),
            ("generate_notifications", {}),
            ("reconcile_balances", {}),
            ("refresh_views", {}),
            ("take_snapshots", {}),
        ]

        for job_name, kwargs in jobs:
            logger.info("startup_job.running job=%s", job_name)
            try:
                call_command(job_name, stdout=self.stdout, **kwargs)
            except Exception:
                logger.exception("startup_job.failed job=%s", job_name)

        logger.info("startup_job.all_complete")
