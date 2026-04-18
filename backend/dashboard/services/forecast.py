"""
Cash flow forecast service — projects future balances based on recurring rules.

ForecastService calculates projected account balances by:
1. Starting with current account balances
2. Projecting all active recurring rules (income and expenses) through end of month
3. Building a day-by-day balance forecast
4. Flagging warnings when projected balance goes negative

Used by DashboardService to show "You have 15,000 EGP. With known flows, you'll have 19,000 by month-end."
"""

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from django.db.models import Sum
from django.db.models.functions import Coalesce

from accounts.models import Account
from core.dates import month_range
from recurring.models import RecurringRule
from recurring.services import RecurringService, _instance_to_rule

logger = logging.getLogger(__name__)


@dataclass
class ForecastDay:
    """Single day in the cash flow forecast."""

    date: date
    balance: float
    change: float = 0.0  # Net change on this day
    events: list[dict[str, Any]] = field(
        default_factory=list
    )  # Rule events on this day
    is_negative: bool = False  # Balance goes negative


@dataclass
class CashFlowForecast:
    """Complete cash flow forecast for the current month."""

    current_balance: float  # Starting balance today
    projected_balance: float  # Projected balance at month end
    change: float  # Net change (projected - current)
    days: list[ForecastDay] = field(default_factory=list)  # Daily breakdown
    has_warning: bool = False  # Any day goes negative
    negative_days: list[date] = field(
        default_factory=list
    )  # Dates with negative balance
    income_total: float = 0.0  # Total projected income
    expense_total: float = 0.0  # Total projected expenses
    currency: str = "EGP"

    @property
    def negative_days_count(self) -> int:
        return len(self.negative_days)


class ForecastService:
    """Calculates cash flow forecasts based on recurring rules.

    Like a simplified version of cash flow planning in traditional finance apps,
    but focused on the current month and driven by existing recurring rules.
    """

    def __init__(self, user_id: str, tz: ZoneInfo) -> None:
        self.user_id = user_id
        self.tz = tz

    def calculate_forecast(
        self,
        account_id: str | None = None,
        include_rules: list[str] | None = None,
        exclude_rules: list[str] | None = None,
    ) -> CashFlowForecast:
        """Calculate cash flow forecast for the current month.

        Args:
            account_id: Optional single account to forecast. If None, forecasts all accounts.
            include_rules: Optional list of rule IDs to include (for "what if" toggle).
            exclude_rules: Optional list of rule IDs to exclude (for "what if" toggle).

        Returns:
            CashFlowForecast with daily projections and summary stats.
        """
        # 1. Get starting balance(s)
        if account_id:
            # Single account forecast
            account = (
                Account.objects.for_user(self.user_id).filter(id=account_id).first()
            )
            if not account:
                raise ValueError(f"Account {account_id} not found")
            current_balance = float(account.current_balance)
            currency = account.currency
        else:
            # All accounts forecast (sum of all EGP accounts)
            from decimal import Decimal

            total = (
                Account.objects.for_user(self.user_id)
                .filter(currency="EGP", is_dormant=False)
                .aggregate(total=Coalesce(Sum("current_balance"), Decimal("0")))
            )
            current_balance = float(total["total"] or 0)
            currency = "EGP"

        # 2. Get month range
        today = date.today()
        month_start, month_end = month_range(today)

        # If we're past the start of the month, start from today
        forecast_start = max(today, month_start)

        # 3. Get active recurring rules for the rest of the month
        rules = self._get_forecast_rules(
            forecast_start, month_end, include_rules, exclude_rules
        )

        # 4. Build day-by-day forecast
        days = self._build_forecast_days(
            current_balance, forecast_start, month_end, rules
        )

        # 5. Calculate summary stats
        projected_balance = days[-1].balance if days else current_balance
        income_total = sum(
            e["amount"] for d in days for e in d.events if e["type"] == "income"
        )
        expense_total = sum(
            e["amount"] for d in days for e in d.events if e["type"] == "expense"
        )
        negative_days = [d.date for d in days if d.is_negative]

        return CashFlowForecast(
            current_balance=current_balance,
            projected_balance=projected_balance,
            change=projected_balance - current_balance,
            days=days,
            has_warning=len(negative_days) > 0,
            negative_days=negative_days,
            income_total=income_total,
            expense_total=expense_total,
            currency=currency,
        )

    def _get_forecast_rules(
        self,
        start_date: date,
        end_date: date,
        include_rules: list[str] | None,
        exclude_rules: list[str] | None,
    ) -> list[dict[str, Any]]:
        """Get active recurring rules with occurrences in the forecast period.

        Args:
            start_date: Forecast start date
            end_date: Forecast end date
            include_rules: Optional whitelist of rule IDs
            exclude_rules: Optional blacklist of rule IDs

        Returns:
            List of dicts with rule metadata and calculated occurrence dates.
        """
        # Base queryset: active rules only
        rules_qs = RecurringRule.objects.for_user(self.user_id).filter(is_active=True)

        # Apply include/exclude filters
        if include_rules:
            rules_qs = rules_qs.filter(id__in=include_rules)
        elif exclude_rules:
            rules_qs = rules_qs.exclude(id__in=exclude_rules)

        rec_svc = RecurringService(self.user_id, self.tz)
        result = []

        for rule_inst in rules_qs:
            # Convert to RecurringRulePending for easier handling
            rule = _instance_to_rule(rule_inst)

            # Skip if no template or missing amount
            tmpl = rule.template_transaction
            if not tmpl or not tmpl.get("amount"):
                continue

            # Calculate occurrences in the forecast period
            occurrences = self._calculate_occurrences(
                rule, start_date, end_date, rec_svc
            )

            if not occurrences:
                continue

            # Determine if this is income or expense
            tx_type = tmpl.get("type", "expense")
            amount = float(tmpl.get("amount", 0))

            result.append(
                {
                    "rule_id": str(rule.id),
                    "type": tx_type,
                    "amount": amount,
                    "note": tmpl.get("note", tx_type),
                    "occurrences": occurrences,
                }
            )

        return result

    def _calculate_occurrences(
        self,
        rule: Any,  # RecurringRulePending
        start_date: date,
        end_date: date,
        rec_svc: RecurringService,
    ) -> list[date]:
        """Calculate all occurrences of a rule within the forecast period.

        Projects the rule's next_due_date forward/backward to find all dates
        within [start_date, end_date].
        """
        occurrences = []
        current = rule.next_due_date

        # If next_due_date is before start_date, advance it
        while current < start_date:
            prev = current
            current = rec_svc._advance_due_date(rule)
            if current <= prev:  # Safety check
                break

        # Collect all occurrences within the period
        while current <= end_date:
            if current >= start_date:
                occurrences.append(current)

            prev = current
            current = rec_svc._advance_due_date(rule)
            if current <= prev:  # Safety check
                break

        return occurrences

    def _build_forecast_days(
        self,
        starting_balance: float,
        start_date: date,
        end_date: date,
        rules: list[dict[str, Any]],
    ) -> list[ForecastDay]:
        """Build day-by-day forecast from rules.

        Args:
            starting_balance: Current balance to start from
            start_date: Forecast start date
            end_date: Forecast end date
            rules: List of rule dicts with occurrences

        Returns:
            List of ForecastDay objects for each day in the period.
        """
        # Build a map of date -> events
        events_by_date: dict[date, list[dict[str, Any]]] = {}

        for rule_data in rules:
            for occ_date in rule_data["occurrences"]:
                if occ_date not in events_by_date:
                    events_by_date[occ_date] = []

                # Positive for income, negative for expense
                amount = rule_data["amount"]
                if rule_data["type"] != "income":
                    amount = -amount

                events_by_date[occ_date].append(
                    {
                        "rule_id": rule_data["rule_id"],
                        "type": rule_data["type"],
                        "amount": abs(rule_data["amount"]),
                        "note": rule_data["note"],
                        "balance_delta": amount,
                    }
                )

        # Build daily forecast
        days = []
        balance = starting_balance
        current_date = start_date

        while current_date <= end_date:
            events = events_by_date.get(current_date, [])
            daily_change = sum(e["balance_delta"] for e in events)
            balance += daily_change

            is_negative = balance < 0
            if is_negative:
                logger.info(
                    "forecast: negative balance on %s: %.2f",
                    current_date,
                    balance,
                )

            days.append(
                ForecastDay(
                    date=current_date,
                    balance=balance,
                    change=daily_change,
                    events=events,
                    is_negative=is_negative,
                )
            )

            current_date += timedelta(days=1)

        return days

    def get_forecast_summary(self) -> dict[str, Any]:
        """Get a concise forecast summary for the dashboard.

        Returns a dict suitable for template rendering with:
        - current_balance: Current total balance
        - projected_balance: Projected month-end balance
        - change: Net change (amount and percentage)
        - has_warning: True if any day goes negative
        - income_total: Total expected income
        - expense_total: Total expected expenses
        - currency: Primary currency
        """
        forecast = self.calculate_forecast()

        change_pct = (
            (forecast.change / forecast.current_balance * 100)
            if forecast.current_balance > 0
            else 0
        )

        return {
            "current_balance": forecast.current_balance,
            "projected_balance": forecast.projected_balance,
            "change": forecast.change,
            "change_pct": change_pct,
            "has_warning": forecast.has_warning,
            "income_total": forecast.income_total,
            "expense_total": forecast.expense_total,
            "currency": forecast.currency,
            "days_count": len(forecast.days),
            "negative_days_count": len(forecast.negative_days),
        }
