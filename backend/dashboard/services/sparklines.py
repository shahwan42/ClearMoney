"""Dashboard sparklines — net worth history, per-currency, per-account sparklines."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from accounts.models import AccountSnapshot
from auth_app.models import HistoricalSnapshot

if TYPE_CHECKING:
    from . import DashboardData


def load_net_worth_history(user_id: str, data: DashboardData, tz: ZoneInfo) -> None:
    """Load net worth sparkline for the selected display currency.

    Updates:
    - data.net_worth_history: Values for selected_currency
    - data.net_worth_change: Percentage change over the period
    """
    if not data.selected_currency:
        return

    # Use existing history from per-currency lookup if already loaded
    if data.selected_currency in data.net_worth_history_by_currency:
        values = data.net_worth_history_by_currency[data.selected_currency]
    else:
        # Load from DB if not already in memory
        today = datetime.now(tz).date()
        start = today - timedelta(days=30)
        rows = (
            HistoricalSnapshot.objects.for_user(user_id)
            .filter(date__gte=start, date__lte=today, currency=data.selected_currency)
            .order_by("date")
            .values_list("net_worth", flat=True)
        )
        values = [float(v) for v in rows]

    if len(values) >= 2:
        data.net_worth_history = values
        oldest = values[0]
        current = values[-1]
        if oldest != 0:
            data.net_worth_change = (current - oldest) / abs(oldest) * 100


def load_net_worth_by_currency(user_id: str, data: DashboardData, tz: ZoneInfo) -> None:
    """Load per-currency net worth history from canonical historical snapshots."""
    today = datetime.now(tz).date()
    start = today - timedelta(days=30)

    rows = (
        HistoricalSnapshot.objects.for_user(user_id)
        .filter(date__gte=start, date__lte=today)
        .order_by("date")
        .values_list("date", "currency", "net_worth")
    )

    if not rows:
        return

    # Group by (date, currency) and sum balances
    from collections import defaultdict

    currency_by_date: dict[str, dict[str, float]] = defaultdict(
        lambda: defaultdict(float)
    )
    for snap_date, currency, balance in rows:
        currency_by_date[currency][str(snap_date)] += float(balance)

    by_currency: dict[str, list[float]] = {}
    for currency, date_totals in currency_by_date.items():
        # Sort by date key to maintain chronological order
        by_currency[currency] = [total for _, total in sorted(date_totals.items())]

    if by_currency:
        data.net_worth_history_by_currency = by_currency


def load_account_sparklines(
    user_id: str, data: DashboardData, all_accounts: list[dict[str, Any]], tz: ZoneInfo
) -> None:
    """Load per-account 30-day balance sparklines."""
    today = datetime.now(tz).date()
    start = today - timedelta(days=30)

    sparklines: dict[str, list[float]] = {}
    for acc in all_accounts:
        rows = (
            AccountSnapshot.objects.for_user(user_id)
            .filter(account_id=acc["id"], date__gte=start, date__lte=today)
            .order_by("date")
            .values_list("balance", flat=True)
        )
        values = [float(r) for r in rows]
        if len(values) >= 2:
            sparklines[acc["id"]] = values

    if sparklines:
        data.account_sparklines = sparklines
