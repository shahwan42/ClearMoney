"""Net worth projection service — calculates future wealth based on patterns."""

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta
from django.db.models import Sum

from core.dates import month_range
from recurring.services import RecurringService
from reports.services import get_month_summary
from transactions.models import Transaction

logger = logging.getLogger(__name__)


class ProjectionService:
    """Calculates projected net worth based on recurring rules and past spending."""

    def __init__(self, user_id: str, tz: ZoneInfo) -> None:
        self.user_id = user_id
        self.tz = tz

    def get_projection(self, current_net_worth: float, months: int = 12) -> dict[str, Any]:
        """Generate net worth projection for the next N months."""
        today = datetime.now(self.tz).date()

        # 1. Calculate average discretionary spending (last 3 months)
        # Discretionary = Total Expenses - Recurring Expenses
        avg_discretionary = self._get_avg_discretionary(today)

        # 2. Get recurring cash flow per month
        recurring_svc = RecurringService(self.user_id, self.tz)

        projection_points = []
        projected_nw = current_net_worth

        milestones = []
        target_milestone = 100000.0 # Example milestone
        reached_milestone = False

        for i in range(1, months + 1):
            target_month = today + relativedelta(months=i)

            # Known recurring for this month
            recurring_events = recurring_svc.get_calendar_data(target_month.year, target_month.month)
            monthly_recurring_net = 0.0
            for event in recurring_events:
                amt = float(event["template_transaction"]["amount"])
                if event["template_transaction"]["type"] == "expense":
                    monthly_recurring_net -= amt
                elif event["template_transaction"]["type"] == "income":
                    monthly_recurring_net += amt

            # Net for this month = recurring_net - avg_discretionary
            monthly_net = monthly_recurring_net - avg_discretionary

            projected_nw += monthly_net

            projection_points.append({
                "month": target_month.strftime("%b %y"),
                "value": projected_nw,
            })

            if not reached_milestone and projected_nw >= target_milestone:
                milestones.append({
                    "title": f"{target_milestone:,.0f} EGP",
                    "date": target_month.strftime("%B %Y"),
                })
                reached_milestone = True

        return {
            "points": projection_points,
            "milestones": milestones,
            "avg_discretionary": avg_discretionary,
        }

    def _get_avg_discretionary(self, today: date) -> float:
        """Calculate average non-recurring spending over the last 3 months."""
        discretionary_totals = []

        for i in range(1, 4):
            dt = today - relativedelta(months=i)
            summary = get_month_summary(self.user_id, dt.year, dt.month)
            total_expenses = summary["expenses"]

            # Recurring expenses for that month
            # We assume recurring rules are consistent.
            # Ideally we check transactions linked to recurring rules.
            recurring_spent = Transaction.objects.for_user(self.user_id).filter(
                date__gte=month_range(dt)[0],
                date__lt=month_range(dt)[1],
                recurring_rule__isnull=False,
                type="expense"
            ).aggregate(total=Sum("amount"))["total"] or Decimal(0)

            discretionary = total_expenses - float(recurring_spent)
            discretionary_totals.append(max(0.0, discretionary))

        if not discretionary_totals:
            return 0.0
        return sum(discretionary_totals) / len(discretionary_totals)
