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
    - USD → EGP conversion using latest exchange rate
    - Excluded virtual account balances subtracted from net worth
"""

import logging
from datetime import date, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db.models import Sum
from django.db.models.functions import Coalesce

from accounts.models import Account, AccountSnapshot
from auth_app.models import DailySnapshot, User
from exchange_rates.models import ExchangeRateLog
from transactions.models import Transaction
from virtual_accounts.models import VirtualAccount

logger = logging.getLogger(__name__)


class SnapshotService:
    """Manages daily balance snapshots — combined service + repository logic."""

    def __init__(self, tz: ZoneInfo) -> None:
        self.tz = tz

    def take_all_user_snapshots(self, days: int = 90) -> int:
        """Take today's snapshot + backfill for all users.

        Iterates all users, takes today's snapshot, then backfills missing days.

        Returns:
            Total number of days backfilled across all users.
        """
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
        """Capture today's financial state as a daily snapshot.

        Safe to call multiple times (update_or_create semantics).
        """
        today = self._today()
        self._take_snapshot_for_date(user_id, today, use_current_balances=True)

    def backfill_snapshots(self, user_id: str, days: int = 90) -> int:
        """Fill in missing daily snapshots for the last N days.

        Historical balances are computed by subtracting future transaction deltas
        from current balance.

        Returns:
            Number of days backfilled (0 if all days already had snapshots).
        """
        today = self._today()
        count = 0

        for i in range(days, -1, -1):
            snapshot_date = today - timedelta(days=i)
            if self._snapshot_exists(user_id, snapshot_date):
                continue

            use_current = i == 0
            try:
                self._take_snapshot_for_date(user_id, snapshot_date, use_current)
                count += 1
            except Exception:
                logger.warning(
                    "snapshot.backfill_day_failed date=%s user_id=%s",
                    snapshot_date.isoformat(),
                    user_id,
                )

        return count

    # ------------------------------------------------------------------
    # Core logic
    # ------------------------------------------------------------------

    def _take_snapshot_for_date(
        self, user_id: str, snapshot_date: date, use_current_balances: bool
    ) -> None:
        """Capture financial state for a specific date.

        Steps:
        1. Get all institutions → accounts for user
        2. Sum balances → net_worth_raw (historical if backfilling)
        3. Track USD total separately
        4. Subtract excluded virtual account balances
        5. Convert USD → EGP using latest exchange rate
        6. Get daily spending/income
        7. Upsert daily + account snapshots
        """
        # Get all accounts grouped by institution
        accounts = self._get_all_accounts(user_id)

        net_worth_raw = 0.0
        usd_total = 0.0
        account_balances: list[tuple[str, float]] = []

        for acc_id, currency, current_balance in accounts:
            if use_current_balances:
                balance = float(current_balance)
            else:
                # Historical: current_balance - future deltas
                future_deltas = self._get_balance_delta_after_date(
                    user_id, acc_id, snapshot_date
                )
                balance = float(current_balance) - future_deltas

            net_worth_raw += balance
            if currency == "USD":
                usd_total += balance
            account_balances.append((acc_id, balance))

        # Subtract excluded virtual account balances
        excluded = self._get_excluded_va_balance(user_id)
        net_worth_raw -= excluded

        # Get exchange rate for USD → EGP conversion
        exchange_rate = self._get_latest_exchange_rate()
        if exchange_rate > 0:
            net_worth_egp = (net_worth_raw - usd_total) + (usd_total * exchange_rate)
        else:
            net_worth_egp = net_worth_raw

        # Get daily spending and income
        spending = self._get_daily_spending(user_id, snapshot_date)
        income = self._get_daily_income(user_id, snapshot_date)

        # Upsert daily snapshot
        self._upsert_daily(
            user_id,
            snapshot_date,
            net_worth_egp,
            net_worth_raw,
            exchange_rate,
            spending,
            income,
        )

        # Upsert per-account snapshots
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
        """Get all user IDs."""
        return [str(uid) for uid in User.objects.values_list("id", flat=True)]

    def _get_all_accounts(self, user_id: str) -> list[tuple[str, str, float]]:
        """Get all non-dormant accounts for a user.

        Returns list of (account_id, currency, current_balance).
        Ordered by institution display_order then account display_order.
        """
        rows = (
            Account.objects.filter(user_id=user_id, is_dormant=False)
            .order_by("institution__display_order", "display_order")
            .values_list("id", "currency", "current_balance")
        )
        return [(str(row[0]), row[1], float(row[2])) for row in rows]

    def _get_balance_delta_after_date(
        self, user_id: str, account_id: str, snapshot_date: date
    ) -> float:
        """Sum of balance_delta for transactions after the given date.

        Used to compute historical balances for backfill.
        """
        total = Transaction.objects.filter(
            user_id=user_id,
            account_id=account_id,
            date__gt=snapshot_date,
        ).aggregate(total=Coalesce(Sum("balance_delta"), Decimal("0")))["total"]
        return float(total)

    def _get_excluded_va_balance(self, user_id: str) -> float:
        """Total balance of VAs excluded from net worth."""
        total = VirtualAccount.objects.filter(
            user_id=user_id,
            exclude_from_net_worth=True,
            is_archived=False,
        ).aggregate(total=Coalesce(Sum("current_balance"), Decimal("0")))["total"]
        return float(total)

    def _get_latest_exchange_rate(self) -> float:
        """Latest USD/EGP exchange rate. No user_id — global data."""
        rate = (
            ExchangeRateLog.objects.order_by("-date", "-created_at")
            .values_list("rate", flat=True)
            .first()
        )
        return float(rate) if rate is not None else 0.0

    def _get_daily_spending(self, user_id: str, snapshot_date: date) -> float:
        """Sum of expense amounts for a given date."""
        total = Transaction.objects.filter(
            user_id=user_id,
            date=snapshot_date,
            type="expense",
        ).aggregate(total=Coalesce(Sum("amount"), Decimal("0")))["total"]
        return float(total)

    def _get_daily_income(self, user_id: str, snapshot_date: date) -> float:
        """Sum of income amounts for a given date."""
        total = Transaction.objects.filter(
            user_id=user_id,
            date=snapshot_date,
            type="income",
        ).aggregate(total=Coalesce(Sum("amount"), Decimal("0")))["total"]
        return float(total)

    def _snapshot_exists(self, user_id: str, snapshot_date: date) -> bool:
        """Check if a daily snapshot already exists."""
        return DailySnapshot.objects.filter(
            user_id=user_id, date=snapshot_date
        ).exists()

    def _upsert_daily(
        self,
        user_id: str,
        snapshot_date: date,
        net_worth_egp: float,
        net_worth_raw: float,
        exchange_rate: float,
        daily_spending: float,
        daily_income: float,
    ) -> None:
        """Upsert a daily snapshot row (idempotent).

        update_or_create issues SELECT + INSERT/UPDATE (two round-trips), unlike
        INSERT ... ON CONFLICT which is atomic. Safe here — the job runs once daily
        and any IntegrityError from a concurrent run is caught by the caller.
        """
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
        self, user_id: str, snapshot_date: date, account_id: str, balance: float
    ) -> None:
        """Upsert an account snapshot row (idempotent). See _upsert_daily for atomicity note."""
        AccountSnapshot.objects.update_or_create(
            user_id=user_id,
            date=snapshot_date,
            account_id=account_id,
            defaults={"balance": balance},
        )

    def _today(self) -> date:
        """Today's date in the configured timezone."""
        from datetime import datetime

        return datetime.now(self.tz).date()
