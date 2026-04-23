"""
Snapshot service — captures daily balance snapshots for all users.

Like Laravel's daily scheduled snapshot job
or Django's management command that captures financial state.

Snapshots power:
    - Net worth sparklines (30-day trend)
    - Per-account balance sparklines
    - Month-over-month comparisons

Key patterns:
    - UPSERT (update_or_create) for idempotency
    - Historical balance = current_balance - SUM(future balance_deltas)
    - Canonical history is stored per date per currency
    - DailySnapshot remains as a legacy compatibility projection
"""

import logging
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import cast
from zoneinfo import ZoneInfo

from django.db.models import Sum
from django.db.models.functions import Coalesce

from accounts.models import Account, AccountSnapshot
from auth_app.models import DailySnapshot, HistoricalSnapshot, User
from exchange_rates.models import ExchangeRateLog
from transactions.models import Transaction
from virtual_accounts.models import VirtualAccount

logger = logging.getLogger(__name__)

ZERO = Decimal("0")


class SnapshotService:
    """Manages daily balance snapshots — combined service + repository logic."""

    def __init__(self, tz: ZoneInfo) -> None:
        self.tz = tz

    def take_all_user_snapshots(self, days: int = 90) -> int:
        """Take today's snapshot + backfill for all users."""
        user_ids = self._get_all_user_ids()
        total_backfilled = 0

        for user_id in user_ids:
            try:
                self.take_snapshot(user_id)
            except Exception:
                logger.exception("snapshot.take_failed user_id=%s", user_id)

            try:
                backfilled = self.backfill_snapshots(user_id, days)
                total_backfilled += backfilled
            except Exception:
                logger.exception("snapshot.backfill_failed user_id=%s", user_id)

        return total_backfilled

    def take_snapshot(self, user_id: str) -> None:
        """Capture today's financial state as a daily snapshot."""
        self._take_snapshot_for_date(user_id, self._today(), use_current_balances=True)

    def backfill_snapshots(self, user_id: str, days: int = 90) -> int:
        """Refresh the last N days and count dates missing canonical history."""
        today = self._today()
        count = 0

        for i in range(days, -1, -1):
            snapshot_date = today - timedelta(days=i)
            use_current = i == 0
            existed = self._historical_snapshot_exists(user_id, snapshot_date)
            try:
                self._take_snapshot_for_date(user_id, snapshot_date, use_current)
                if not existed:
                    count += 1
            except Exception:
                logger.warning(
                    "snapshot.backfill_day_failed date=%s user_id=%s",
                    snapshot_date.isoformat(),
                    user_id,
                )

        return count

    def backfill_historical_snapshots_from_account_snapshots(self, user_id: str) -> int:
        """Rebuild canonical per-currency history from stored account snapshots."""
        totals_by_date: dict[date, dict[str, Decimal]] = defaultdict(
            lambda: defaultdict(lambda: ZERO)
        )
        rows = (
            AccountSnapshot.objects.filter(user_id=user_id)
            .select_related("account")
            .order_by("date", "account__currency")
            .values_list("date", "account__currency", "balance")
        )
        for snapshot_date, currency, balance in rows:
            totals_by_date[snapshot_date][currency] += balance

        today = self._today()
        if today not in totals_by_date:
            current_totals: dict[str, Decimal] = defaultdict(lambda: ZERO)
            for _account_id, currency, balance in self._get_all_accounts(user_id):
                current_totals[currency] += balance
            current_totals["EGP"] = current_totals.get(
                "EGP", ZERO
            ) - self._get_excluded_va_balance(user_id)
            if current_totals:
                totals_by_date[today] = current_totals

        daily_expense_rows = self._get_daily_transaction_rows(user_id, "expense")
        daily_income_rows = self._get_daily_transaction_rows(user_id, "income")

        for snapshot_date, totals in totals_by_date.items():
            self._sync_historical_snapshots(
                user_id=user_id,
                snapshot_date=snapshot_date,
                totals_by_currency=dict(totals),
                spending_by_currency=daily_expense_rows.get(snapshot_date, {}),
                income_by_currency=daily_income_rows.get(snapshot_date, {}),
            )

        return len(totals_by_date)

    # ------------------------------------------------------------------
    # Core logic
    # ------------------------------------------------------------------

    def _take_snapshot_for_date(
        self, user_id: str, snapshot_date: date, use_current_balances: bool
    ) -> None:
        """Capture financial state for a specific date."""
        accounts = self._get_all_accounts(user_id)

        net_worth_raw = ZERO
        totals_by_currency: dict[str, Decimal] = defaultdict(lambda: ZERO)
        account_balances: list[tuple[str, Decimal]] = []

        for acc_id, currency, current_balance in accounts:
            balance = current_balance
            if not use_current_balances:
                balance -= self._get_balance_delta_after_date(
                    user_id, acc_id, snapshot_date
                )

            net_worth_raw += balance
            totals_by_currency[currency] += balance
            account_balances.append((acc_id, balance))

        excluded = self._get_excluded_va_balance(user_id)
        net_worth_raw -= excluded
        totals_by_currency["EGP"] = totals_by_currency.get("EGP", ZERO) - excluded

        exchange_rate = self._get_latest_exchange_rate()
        net_worth_egp = self._convert_totals_to_egp(
            dict(totals_by_currency), exchange_rate
        )

        spending_by_currency = self._get_daily_total_by_currency(
            user_id, snapshot_date, "expense"
        )
        income_by_currency = self._get_daily_total_by_currency(
            user_id, snapshot_date, "income"
        )
        daily_spending = sum(spending_by_currency.values(), start=ZERO)
        daily_income = sum(income_by_currency.values(), start=ZERO)

        self._sync_historical_snapshots(
            user_id=user_id,
            snapshot_date=snapshot_date,
            totals_by_currency=dict(totals_by_currency),
            spending_by_currency=spending_by_currency,
            income_by_currency=income_by_currency,
        )

        self._upsert_daily(
            user_id=user_id,
            snapshot_date=snapshot_date,
            net_worth_egp=net_worth_egp,
            net_worth_raw=net_worth_raw,
            exchange_rate=exchange_rate,
            daily_spending=daily_spending,
            daily_income=daily_income,
        )

        for acc_id, balance in account_balances:
            try:
                self._upsert_account(user_id, snapshot_date, acc_id, balance)
            except Exception:
                logger.error(
                    "snapshot.account_failed account_id=%s date=%s",
                    acc_id,
                    snapshot_date.isoformat(),
                )

    # ------------------------------------------------------------------
    # ORM queries
    # ------------------------------------------------------------------

    def _get_all_user_ids(self) -> list[str]:
        return [str(uid) for uid in User.objects.values_list("id", flat=True)]

    def _get_all_accounts(self, user_id: str) -> list[tuple[str, str, Decimal]]:
        rows = (
            Account.objects.filter(user_id=user_id, is_dormant=False)
            .order_by("institution__display_order", "display_order")
            .values_list("id", "currency", "current_balance")
        )
        return [(str(row[0]), row[1], row[2]) for row in rows]

    def _get_balance_delta_after_date(
        self, user_id: str, account_id: str, snapshot_date: date
    ) -> Decimal:
        total = Transaction.objects.filter(
            user_id=user_id,
            account_id=account_id,
            date__gt=snapshot_date,
        ).aggregate(total=Coalesce(Sum("balance_delta"), ZERO))["total"]
        return cast(Decimal, total)

    def _get_excluded_va_balance(self, user_id: str) -> Decimal:
        total = VirtualAccount.objects.filter(
            user_id=user_id,
            exclude_from_net_worth=True,
            is_archived=False,
        ).aggregate(total=Coalesce(Sum("current_balance"), ZERO))["total"]
        return cast(Decimal, total)

    def _get_latest_exchange_rate(self) -> Decimal:
        rate = (
            ExchangeRateLog.objects.order_by("-date", "-created_at")
            .values_list("rate", flat=True)
            .first()
        )
        return rate if rate is not None else ZERO

    def _get_daily_total_by_currency(
        self, user_id: str, snapshot_date: date, tx_type: str
    ) -> dict[str, Decimal]:
        rows = Transaction.objects.filter(
            user_id=user_id,
            date=snapshot_date,
            type=tx_type,
        ).values_list("currency", "amount")
        totals: dict[str, Decimal] = defaultdict(lambda: ZERO)
        for currency, amount in rows:
            totals[currency] += amount
        return dict(totals)

    def _get_daily_transaction_rows(
        self, user_id: str, tx_type: str
    ) -> dict[date, dict[str, Decimal]]:
        rows = Transaction.objects.filter(user_id=user_id, type=tx_type).values_list(
            "date", "currency", "amount"
        )
        totals_by_date: dict[date, dict[str, Decimal]] = defaultdict(
            lambda: defaultdict(lambda: ZERO)
        )
        for tx_date, currency, amount in rows:
            totals_by_date[tx_date][currency] += amount
        return {
            tx_date: dict(currency_totals)
            for tx_date, currency_totals in totals_by_date.items()
        }

    def _historical_snapshot_exists(self, user_id: str, snapshot_date: date) -> bool:
        return HistoricalSnapshot.objects.filter(
            user_id=user_id, date=snapshot_date
        ).exists()

    def _convert_totals_to_egp(
        self, totals_by_currency: dict[str, Decimal], exchange_rate: Decimal
    ) -> Decimal:
        net_worth_egp = ZERO
        for currency, total in totals_by_currency.items():
            if currency == "USD" and exchange_rate > ZERO:
                net_worth_egp += total * exchange_rate
            else:
                net_worth_egp += total
        return net_worth_egp

    def _sync_historical_snapshots(
        self,
        user_id: str,
        snapshot_date: date,
        totals_by_currency: dict[str, Decimal],
        spending_by_currency: dict[str, Decimal],
        income_by_currency: dict[str, Decimal],
    ) -> None:
        active_currencies = {
            *totals_by_currency.keys(),
            *spending_by_currency.keys(),
            *income_by_currency.keys(),
        }
        if not active_currencies:
            HistoricalSnapshot.objects.filter(
                user_id=user_id, date=snapshot_date
            ).delete()
            return

        for currency in active_currencies:
            HistoricalSnapshot.objects.update_or_create(
                user_id=user_id,
                date=snapshot_date,
                currency=currency,
                defaults={
                    "net_worth": totals_by_currency.get(currency, ZERO),
                    "daily_spending": spending_by_currency.get(currency, ZERO),
                    "daily_income": income_by_currency.get(currency, ZERO),
                },
            )

        HistoricalSnapshot.objects.filter(user_id=user_id, date=snapshot_date).exclude(
            currency__in=active_currencies
        ).delete()

    def _upsert_daily(
        self,
        user_id: str,
        snapshot_date: date,
        net_worth_egp: Decimal,
        net_worth_raw: Decimal,
        exchange_rate: Decimal,
        daily_spending: Decimal,
        daily_income: Decimal,
    ) -> None:
        DailySnapshot.objects.update_or_create(
            user_id=user_id,
            date=snapshot_date,
            defaults={
                "net_worth_egp": net_worth_egp,
                "net_worth_raw": net_worth_raw,
                "exchange_rate": exchange_rate,
                "daily_spending": daily_spending,
                "daily_income": daily_income,
            },
        )

    def _upsert_account(
        self, user_id: str, snapshot_date: date, account_id: str, balance: Decimal
    ) -> None:
        AccountSnapshot.objects.update_or_create(
            user_id=user_id,
            date=snapshot_date,
            account_id=account_id,
            defaults={"balance": balance},
        )

    def _today(self) -> date:
        from datetime import datetime

        return datetime.now(self.tz).date()
