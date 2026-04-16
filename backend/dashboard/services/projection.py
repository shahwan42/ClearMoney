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

# Scenario multipliers for optimistic / pessimistic projections
_OPTIMISTIC_DISCRETIONARY_FACTOR = 0.8   # 20% less discretionary spending
_PESSIMISTIC_DISCRETIONARY_FACTOR = 1.2  # 20% more discretionary spending


class ProjectionService:
    """Calculates projected net worth based on recurring rules and past spending."""

    def __init__(self, user_id: str, tz: ZoneInfo) -> None:
        self.user_id = user_id
        self.tz = tz

    def get_projection(self, current_net_worth: float, months: int = 12) -> dict[str, Any]:
        """Generate net worth projection for the next N months.

        Returns three scenarios (expected, optimistic, pessimistic) and any
        milestone markers for the expected scenario.
        """
        today = datetime.now(self.tz).date()

        # Average discretionary spending (last 3 months)
        avg_discretionary = self._get_avg_discretionary(today)

        recurring_svc = RecurringService(self.user_id, self.tz)

        # Build monthly recurring cash flow cache
        monthly_recurring: list[float] = []
        for i in range(1, months + 1):
            target_month = today + relativedelta(months=i)
            recurring_events = recurring_svc.get_calendar_data(target_month.year, target_month.month)
            monthly_net = 0.0
            for event in recurring_events:
                amt = float(event["template_transaction"]["amount"])
                if event["template_transaction"]["type"] == "expense":
                    monthly_net -= amt
                elif event["template_transaction"]["type"] == "income":
                    monthly_net += amt
            monthly_recurring.append(monthly_net)

        # Generate milestones from net worth tiers above current
        milestone_targets = self._get_milestone_targets(current_net_worth)

        # Build scenario trajectories
        expected_points = []
        optimistic_points = []
        pessimistic_points = []
        milestones: list[dict[str, str]] = []
        reached = set()

        nw_exp = current_net_worth
        nw_opt = current_net_worth
        nw_pes = current_net_worth

        for i in range(months):
            target_month = today + relativedelta(months=i + 1)
            rec = monthly_recurring[i]

            month_label = target_month.strftime("%b %y")

            nw_exp += rec - avg_discretionary
            nw_opt += rec - avg_discretionary * _OPTIMISTIC_DISCRETIONARY_FACTOR
            nw_pes += rec - avg_discretionary * _PESSIMISTIC_DISCRETIONARY_FACTOR

            # Each point includes all three scenarios for easy template access
            expected_points.append({
                "month": month_label,
                "value": nw_exp,
                "optimistic": nw_opt,
                "pessimistic": nw_pes,
            })
            optimistic_points.append({"month": month_label, "value": nw_opt})
            pessimistic_points.append({"month": month_label, "value": nw_pes})

            for target in milestone_targets:
                if target not in reached and nw_exp >= target:
                    reached.add(target)
                    milestones.append({
                        "title": f"{target:,.0f} EGP",
                        "date": target_month.strftime("%B %Y"),
                    })

        return {
            "points": expected_points,
            "optimistic_points": optimistic_points,
            "pessimistic_points": pessimistic_points,
            "milestones": milestones,
            "avg_discretionary": avg_discretionary,
        }

    def _get_milestone_targets(self, current_net_worth: float) -> list[float]:
        """Return the next 3 round-number milestones above current net worth."""
        if current_net_worth <= 0:
            tiers = [10_000, 50_000, 100_000, 250_000, 500_000, 1_000_000]
        elif current_net_worth < 100_000:
            tiers = [50_000, 100_000, 250_000, 500_000, 1_000_000]
        elif current_net_worth < 500_000:
            tiers = [250_000, 500_000, 1_000_000, 2_000_000]
        else:
            # Round up to next million
            next_m = (int(current_net_worth // 1_000_000) + 1) * 1_000_000
            tiers = [next_m, next_m * 2, next_m * 5]
        return [float(t) for t in tiers if t > current_net_worth][:3]

    def _get_avg_discretionary(self, today: date) -> float:
        """Calculate average non-recurring spending over the last 3 months."""
        discretionary_totals = []

        for i in range(1, 4):
            dt = today - relativedelta(months=i)
            summary = get_month_summary(self.user_id, dt.year, dt.month)
            total_expenses = summary["expenses"]

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
