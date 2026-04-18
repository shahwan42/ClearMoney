"""Dashboard activity — people summary, streak tracking, recent transactions.

Streak and recent transaction logic is owned by the transactions service.
This module re-exports their types for backward compatibility and handles
people summary (which is dashboard-specific aggregation).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from people.models import Person

# Re-export from transactions service (canonical location)
from transactions.services.activity import (
    StreakInfo,  # noqa: F401
    TransactionRow,  # noqa: F401
    load_recent_transactions,  # noqa: F401
    load_streak,  # noqa: F401
)

if TYPE_CHECKING:
    from . import DashboardData


@dataclass
class PeopleCurrencySummary:
    """Per-currency people ledger totals."""

    currency: str
    owed_to_me: float = 0.0
    i_owe: float = 0.0


def load_people_summary(user_id: str, data: DashboardData) -> None:
    """Load people ledger grouped by currency."""
    rows = (
        Person.objects.for_user(user_id)
        .order_by("name")
        .values_list("name", "net_balance", "net_balance_egp", "net_balance_usd")
    )

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
            data.debt_egp += abs(nb_egp)

        if nb_usd > 0:
            usd.owed_to_me += nb_usd
        elif nb_usd < 0:
            usd.i_owe += nb_usd
            data.debt_usd += abs(nb_usd)

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


# load_streak and load_recent_transactions are re-exported from
# transactions.services.activity (see imports above).
