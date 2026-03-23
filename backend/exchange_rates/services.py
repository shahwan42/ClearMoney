"""
Exchange rate service — read-only queries for exchange rate history.

Like Laravel's ExchangeRateService — wraps ORM queries.

Key design: Exchange rates are global data (no user_id). The service only
needs a timezone for consistent date handling, not user scoping.
"""

import logging
from typing import Any
from zoneinfo import ZoneInfo

from core.models import ExchangeRateLog

logger = logging.getLogger(__name__)


class ExchangeRateService:
    """Read-only access to the exchange rate log.

    Unlike most services, this has no user_id — exchange rates are global.
    """

    def __init__(self, tz: ZoneInfo) -> None:
        self.tz = tz

    def get_all(self) -> list[dict[str, Any]]:
        """Fetch recent exchange rates, newest first.

        Returns up to 100 rows ordered by created_at DESC.
        """
        rows = ExchangeRateLog.objects.order_by("-created_at").values(
            "id", "date", "rate", "source", "note", "created_at"
        )[:100]

        return [
            {
                "id": str(row["id"]),
                "date": row["date"],
                "rate": float(row["rate"]),
                "source": row["source"],
                "note": row["note"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]
