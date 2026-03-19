"""
Exchange rate service — read-only queries for exchange rate history.

Port of Go's ExchangeRateRepo.GetAll (internal/repository/exchange_rate.go).
Like Laravel's ExchangeRateService — wraps raw SQL queries.

Key design: Exchange rates are global data (no user_id). The service only
needs a timezone for consistent date handling, not user scoping.
"""

import logging
from typing import Any
from zoneinfo import ZoneInfo

from django.db import connection

logger = logging.getLogger(__name__)


class ExchangeRateService:
    """Read-only access to the exchange rate log.

    Unlike most services, this has no user_id — exchange rates are global.
    """

    def __init__(self, tz: ZoneInfo) -> None:
        self.tz = tz

    def get_all(self) -> list[dict[str, Any]]:
        """Fetch recent exchange rates, newest first.

        Port of Go's ExchangeRateRepo.GetAll (exchange_rate.go).
        Returns up to 100 rows ordered by created_at DESC.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, date, rate, source, note, created_at
                FROM exchange_rate_log
                ORDER BY created_at DESC
                LIMIT 100
                """
            )
            rows = cursor.fetchall()

        return [
            {
                "id": str(row[0]),
                "date": row[1],
                "rate": float(row[2]),
                "source": row[3],
                "note": row[4],
                "created_at": row[5],
            }
            for row in rows
        ]
