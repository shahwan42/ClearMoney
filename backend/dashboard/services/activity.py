"""Dashboard activity — people summary, streak tracking, recent transactions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from django.db import connection

if TYPE_CHECKING:
    from . import DashboardData


@dataclass
class PeopleCurrencySummary:
    """Per-currency people ledger totals."""

    currency: str
    owed_to_me: float = 0.0
    i_owe: float = 0.0


@dataclass
class StreakInfo:
    """Habit tracking — consecutive days with transactions."""

    consecutive_days: int = 0
    weekly_count: int = 0
    active_today: bool = False


@dataclass
class TransactionRow:
    """Recent transaction display row with running balance."""

    id: str
    type: str
    amount: float
    currency: str
    date: date
    note: str | None
    balance_delta: float
    account_name: str
    running_balance: float


def load_people_summary(user_id: str, data: DashboardData) -> None:
    """Load people ledger grouped by currency."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT name, net_balance, net_balance_egp, net_balance_usd
            FROM persons WHERE user_id = %s ORDER BY name
            """,
            [user_id],
        )
        rows = cursor.fetchall()

    egp = PeopleCurrencySummary(currency="EGP")
    usd = PeopleCurrencySummary(currency="USD")

    for _name, net_balance, net_balance_egp, net_balance_usd in rows:
        nb = float(net_balance)
        nb_egp = float(net_balance_egp)
        nb_usd = float(net_balance_usd)

        if nb_egp > 0:
            egp.owed_to_me += nb_egp
        elif nb_egp < 0:
            egp.i_owe += nb_egp

        if nb_usd > 0:
            usd.owed_to_me += nb_usd
        elif nb_usd < 0:
            usd.i_owe += nb_usd

        if nb > 0:
            data.people_owed_to_me += nb
        elif nb < 0:
            data.people_i_owe += nb

    if egp.owed_to_me != 0 or egp.i_owe != 0:
        data.people_by_currency.append(egp)
    if usd.owed_to_me != 0 or usd.i_owe != 0:
        data.people_by_currency.append(usd)

    data.has_people_activity = (
        len(data.people_by_currency) > 0
        or data.people_owed_to_me != 0
        or data.people_i_owe != 0
    )


def load_streak(user_id: str, tz: ZoneInfo) -> StreakInfo:
    """Compute consecutive days with transactions + weekly count.

    Uses a backward-walking algorithm over the last 365 days.
    """
    info = StreakInfo()
    now = datetime.now(tz)
    today = now.date()

    with connection.cursor() as cursor:
        # Distinct transaction dates, descending
        cursor.execute(
            """
            SELECT DISTINCT date::date AS d FROM transactions
            WHERE date <= %s AND user_id = %s
            ORDER BY d DESC LIMIT 365
            """,
            [today, user_id],
        )
        dates = [row[0] for row in cursor.fetchall()]

    if not dates:
        return info

    expected = today
    for d in dates:
        if d == expected:
            info.consecutive_days += 1
            if expected == today:
                info.active_today = True
            expected -= timedelta(days=1)
        elif d < expected:
            # Grace period: if no tx today but yesterday has one
            if info.consecutive_days == 0 and d == today - timedelta(days=1):
                info.consecutive_days += 1
                expected = d - timedelta(days=1)
            else:
                break

    # Weekly count (Mon-Sun)
    weekday = now.weekday()  # 0=Mon, 6=Sun
    monday = today - timedelta(days=weekday)
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT COUNT(*) FROM transactions
            WHERE date >= %s AND date <= %s AND user_id = %s
            """,
            [monday, today, user_id],
        )
        row = cursor.fetchone()
        info.weekly_count = row[0] if row else 0

    return info


def load_recent_transactions(user_id: str, limit: int = 10) -> list[TransactionRow]:
    """Load recent transactions with running balance.

    Uses a window function to compute running balance per account.
    Called by the partial view directly.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT sub.id, sub.type, sub.amount, sub.currency, sub.date,
                   sub.note, sub.balance_delta, sub.account_name, sub.running_balance
            FROM (
                SELECT t.id, t.type, t.amount, t.currency, t.date, t.note,
                       t.balance_delta, a.name AS account_name,
                       a.current_balance - COALESCE(
                           SUM(t.balance_delta) OVER (
                               PARTITION BY t.account_id
                               ORDER BY t.date DESC, t.created_at DESC
                               ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                           ), 0
                       ) AS running_balance
                FROM transactions t
                JOIN accounts a ON a.id = t.account_id
                WHERE t.user_id = %s
            ) sub
            ORDER BY sub.date DESC, sub.id DESC
            LIMIT %s
            """,
            [user_id, limit],
        )
        rows = cursor.fetchall()

    return [
        TransactionRow(
            id=str(row[0]),
            type=row[1],
            amount=float(row[2]),
            currency=row[3],
            date=row[4],
            note=row[5],
            balance_delta=float(row[6]),
            account_name=row[7],
            running_balance=float(row[8]),
        )
        for row in rows
    ]
