"""Calendar service — aggregates financial events for the calendar view."""

import logging
from datetime import date
from typing import Any
from zoneinfo import ZoneInfo

from core.dates import month_range
from recurring.services import RecurringService
from transactions.models import Transaction

logger = logging.getLogger(__name__)


class CalendarService:
    """Aggregates transactions, recurring rules, and other events."""

    def __init__(self, user_id: str, tz: ZoneInfo) -> None:
        self.user_id = user_id
        self.tz = tz

    def get_month_events(
        self, year: int, month: int
    ) -> dict[int, list[dict[str, Any]]]:
        """Get all financial events for a specific month, grouped by day."""
        start_date, end_date = month_range(date(year, month, 1))

        events_by_day: dict[int, list[dict[str, Any]]] = {}

        # 1. Recurring Rules (Projections)
        recurring_svc = RecurringService(self.user_id, self.tz)
        upcoming = recurring_svc.get_calendar_data(year, month)
        for occ in upcoming:
            day = occ["day"]
            if day not in events_by_day:
                events_by_day[day] = []

            # Format as event
            events_by_day[day].append(
                {
                    "type": "recurring",
                    "subtype": occ["template_transaction"]["type"],
                    "title": occ["note"],
                    "amount": occ["template_transaction"]["amount"],
                    "currency": occ["template_transaction"]["currency"],
                    "is_projection": True,
                }
            )

        # 2. Actual Transactions
        txs = (
            Transaction.objects.for_user(self.user_id)
            .filter(
                date__gte=start_date,
                date__lt=end_date,
            )
            .select_related("category")
        )

        for tx in txs:
            day = tx.date.day
            if day not in events_by_day:
                events_by_day[day] = []

            events_by_day[day].append(
                {
                    "type": "transaction",
                    "subtype": tx.type,
                    "title": tx.note
                    or (tx.category.get_display_name() if tx.category else tx.type),
                    "amount": float(tx.amount),
                    "currency": tx.currency,
                    "is_projection": False,
                }
            )

        # 3. Budget Resets (1st of month)
        events_by_day[1] = events_by_day.get(1, [])
        events_by_day[1].append(
            {
                "type": "event",
                "subtype": "info",
                "title": "Budget Reset",
                "is_projection": True,
            }
        )

        return events_by_day
