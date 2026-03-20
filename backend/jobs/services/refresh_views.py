"""
Refresh materialized views service — keeps pre-aggregated data up to date.

Materialized views are database-level cached queries. Unlike regular views,
results are stored on disk for fast reads but must be manually refreshed.

Our views:
    - mv_monthly_category_totals: monthly spending by category (powers Reports)
    - mv_daily_tx_counts: daily transaction counts (powers Streak tracker)

Strategy: try CONCURRENTLY first (allows reads during refresh), fall back to
regular REFRESH (locks view, needed for first population).

Like Django's django-cachalot or manually caching QuerySet results in Redis,
but done at the PostgreSQL level.
"""

import logging

from django.db import connection

logger = logging.getLogger(__name__)

# View names are hardcoded — safe for string formatting in DDL
# (PostgreSQL doesn't support parameterized DDL statements).
VIEWS = ["mv_monthly_category_totals", "mv_daily_tx_counts"]


class RefreshViewsService:
    """Refreshes PostgreSQL materialized views for dashboard and reports."""

    def refresh(self) -> None:
        """Refresh all materialized views.

        Tries CONCURRENTLY first (non-blocking reads), falls back to
        regular REFRESH (needed when view has never been populated).
        """
        with connection.cursor() as cursor:
            for view in VIEWS:
                try:
                    cursor.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view}")
                    logger.info("refresh_views.refreshed view=%s mode=concurrent", view)
                except Exception:
                    logger.warning(
                        "refresh_views.concurrent_failed view=%s, retrying without CONCURRENTLY",
                        view,
                    )
                    cursor.execute(f"REFRESH MATERIALIZED VIEW {view}")
                    logger.info("refresh_views.refreshed view=%s mode=regular", view)
