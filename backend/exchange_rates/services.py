"""
Exchange rate service — read-only queries for exchange rate history.

Like Laravel's ExchangeRateService — wraps ORM queries.

Key design: Exchange rates are global data (no user_id). The service only
needs a timezone for consistent date handling, not user scoping.
"""

import logging
from typing import Any
from zoneinfo import ZoneInfo

from core.serializers import serialize_row
from exchange_rates.models import ExchangeRateLog

logger = logging.getLogger(__name__)

_EXCHANGE_RATE_FIELDS = ("id", "date", "rate", "source", "note", "created_at")


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
            *_EXCHANGE_RATE_FIELDS
        )[:100]

        return [
            serialize_row(row, {f: f for f in _EXCHANGE_RATE_FIELDS}) for row in rows
        ]
