"""Dashboard sparklines — net worth history, per-currency, per-account sparklines."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from django.db import connection

if TYPE_CHECKING:
    from . import DashboardData


def load_net_worth_history(user_id: str, data: DashboardData, tz: ZoneInfo) -> None:
    """Load 30-day net worth sparkline from daily_snapshots."""
    today = datetime.now(tz).date()
    start = today - timedelta(days=30)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT net_worth_egp FROM daily_snapshots
            WHERE date >= %s AND date <= %s AND user_id = %s
            ORDER BY date ASC
            """,
            [start, today, user_id],
        )
        rows = cursor.fetchall()

    if len(rows) >= 2:
        values = [float(r[0]) for r in rows]
        data.net_worth_history = values
        oldest = values[0]
        current = values[-1]
        if oldest != 0:
            data.net_worth_change = (current - oldest) / abs(oldest) * 100


def load_net_worth_by_currency(user_id: str, data: DashboardData, tz: ZoneInfo) -> None:
    """Load per-currency net worth history for dual sparkline."""
    today = datetime.now(tz).date()
    start = today - timedelta(days=30)

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT s.date, a.currency, SUM(s.balance) as total
            FROM account_snapshots s
            JOIN accounts a ON a.id = s.account_id
            WHERE s.date >= %s AND s.date <= %s AND s.user_id = %s
            GROUP BY s.date, a.currency
            ORDER BY s.date ASC
            """,
            [start, today, user_id],
        )
        rows = cursor.fetchall()

    if not rows:
        return

    by_currency: dict[str, list[float]] = {}
    # Group by currency, ordered by date
    for _date, currency, total in rows:
        by_currency.setdefault(currency, []).append(float(total))

    if by_currency:
        data.net_worth_history_by_currency = by_currency


def load_account_sparklines(
    user_id: str, data: DashboardData, all_accounts: list[dict[str, Any]], tz: ZoneInfo
) -> None:
    """Load per-account 30-day balance sparklines."""
    today = datetime.now(tz).date()
    start = today - timedelta(days=30)

    sparklines: dict[str, list[float]] = {}
    with connection.cursor() as cursor:
        for acc in all_accounts:
            cursor.execute(
                """
                SELECT balance FROM account_snapshots
                WHERE account_id = %s AND date >= %s AND date <= %s AND user_id = %s
                ORDER BY date ASC
                """,
                [acc["id"], start, today, user_id],
            )
            rows = cursor.fetchall()
            if len(rows) >= 2:
                sparklines[acc["id"]] = [float(r[0]) for r in rows]

    if sparklines:
        data.account_sparklines = sparklines
