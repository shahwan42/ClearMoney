"""
Management command: refresh_views — refresh PostgreSQL materialized views.

Port of Go's RefreshMaterializedViews() (internal/jobs/refresh_views.go).
Refreshes mv_monthly_category_totals and mv_daily_tx_counts for fast
dashboard and report queries.

Usage:
    python manage.py refresh_views
"""

from typing import Any

from django.core.management.base import BaseCommand

from jobs.services.refresh_views import RefreshViewsService


class Command(BaseCommand):
    help = "Refresh PostgreSQL materialized views (category totals, daily tx counts)"

    def handle(self, *args: Any, **options: Any) -> None:
        svc = RefreshViewsService()
        svc.refresh()
        self.stdout.write(
            self.style.SUCCESS("Materialized views refreshed successfully")
        )
