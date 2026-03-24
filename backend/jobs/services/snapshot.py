"""
Snapshot service — captures daily balance snapshots for all users.

Like Laravel's daily scheduled snapshot job
or Django's management command that captures financial state.

Snapshots power:
    - Net worth sparklines (30-day trend)
    - Per-account balance sparklines
    - Month-over-month comparisons

Key patterns:
    - UPSERT (INSERT ... ON CONFLICT DO UPDATE) for idempotency
    - Historical balance = current_balance - SUM(future balance_deltas)
    - USD → EGP conversion using latest exchange rate
    - Excluded virtual account balances subtracted from net worth
"""

import logging
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from django.db import connection

logger = logging.getLogger(__name__)


class SnapshotService:
    """Manages daily balance snapshots — combined service + repository logic.

    All SQL queries are inline (raw SQL via django.db.connection),
    consistent with other Django services.
    """

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

        Safe to call multiple times (UPSERT semantics).
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
        7. UPSERT daily + account snapshots
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

        # UPSERT daily snapshot
        self._upsert_daily(
            user_id,
            snapshot_date,
            net_worth_egp,
            net_worth_raw,
            exchange_rate,
            spending,
            income,
        )

        # UPSERT per-account snapshots
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
    # SQL queries
    # ------------------------------------------------------------------

    def _get_all_user_ids(self) -> list[str]:
        """Get all user IDs."""
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM users")
            return [str(row[0]) for row in cursor.fetchall()]

    def _get_all_accounts(self, user_id: str) -> list[tuple[str, str, float]]:
        """Get all non-dormant accounts for a user.

        Returns list of (account_id, currency, current_balance).
        Iterates via institutions like Go does (institutions → accounts).
        """
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT a.id, a.currency, a.current_balance
                   FROM accounts a
                   JOIN institutions i ON a.institution_id = i.id
                   WHERE a.user_id = %s AND a.is_dormant = false
                   ORDER BY i.display_order, a.display_order""",
                [user_id],
            )
            return [(str(row[0]), row[1], float(row[2])) for row in cursor.fetchall()]

    def _get_balance_delta_after_date(
        self, user_id: str, account_id: str, snapshot_date: date
    ) -> float:
        """Sum of balance_delta for transactions after the given date.

        Used to compute historical balances for backfill.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT COALESCE(SUM(balance_delta), 0)
                   FROM transactions
                   WHERE account_id = %s AND date::date > %s::date AND user_id = %s""",
                [account_id, snapshot_date, user_id],
            )
            row = cursor.fetchone()
            return float(row[0]) if row else 0.0

    def _get_excluded_va_balance(self, user_id: str) -> float:
        """Total balance of VAs excluded from net worth."""
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT COALESCE(SUM(current_balance), 0)
                   FROM virtual_accounts
                   WHERE exclude_from_net_worth = true
                     AND is_archived = false
                     AND user_id = %s""",
                [user_id],
            )
            row = cursor.fetchone()
            return float(row[0]) if row else 0.0

    def _get_latest_exchange_rate(self) -> float:
        """Latest USD/EGP exchange rate. No user_id — global data."""
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT rate FROM exchange_rate_log ORDER BY date DESC, created_at DESC LIMIT 1"
            )
            row = cursor.fetchone()
            return float(row[0]) if row else 0.0

    def _get_daily_spending(self, user_id: str, snapshot_date: date) -> float:
        """Sum of expense amounts for a given date."""
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT COALESCE(SUM(amount), 0)
                   FROM transactions
                   WHERE date::date = %s::date AND type = 'expense' AND user_id = %s""",
                [snapshot_date, user_id],
            )
            row = cursor.fetchone()
            return float(row[0]) if row else 0.0

    def _get_daily_income(self, user_id: str, snapshot_date: date) -> float:
        """Sum of income amounts for a given date."""
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT COALESCE(SUM(amount), 0)
                   FROM transactions
                   WHERE date::date = %s::date AND type = 'income' AND user_id = %s""",
                [snapshot_date, user_id],
            )
            row = cursor.fetchone()
            return float(row[0]) if row else 0.0

    def _snapshot_exists(self, user_id: str, snapshot_date: date) -> bool:
        """Check if a daily snapshot already exists."""
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT EXISTS(SELECT 1 FROM daily_snapshots WHERE date = %s AND user_id = %s)",
                [snapshot_date, user_id],
            )
            row = cursor.fetchone()
            return bool(row[0]) if row else False

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
        """UPSERT a daily snapshot row.

        ON CONFLICT (date, user_id) DO UPDATE ensures idempotency.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO daily_snapshots
                       (user_id, date, net_worth_egp, net_worth_raw,
                        exchange_rate, daily_spending, daily_income)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (date, user_id) DO UPDATE SET
                       net_worth_egp = EXCLUDED.net_worth_egp,
                       net_worth_raw = EXCLUDED.net_worth_raw,
                       exchange_rate = EXCLUDED.exchange_rate,
                       daily_spending = EXCLUDED.daily_spending,
                       daily_income = EXCLUDED.daily_income""",
                [
                    user_id,
                    snapshot_date,
                    net_worth_egp,
                    net_worth_raw,
                    exchange_rate,
                    daily_spending,
                    daily_income,
                ],
            )

    def _upsert_account(
        self, user_id: str, snapshot_date: date, account_id: str, balance: float
    ) -> None:
        """UPSERT an account snapshot row.

        ON CONFLICT (date, account_id) DO UPDATE ensures idempotency.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO account_snapshots (user_id, date, account_id, balance)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (user_id, date, account_id) DO UPDATE SET
                       balance = EXCLUDED.balance""",
                [user_id, snapshot_date, account_id, balance],
            )

    def _today(self) -> date:
        """Today's date in the configured timezone."""
        from datetime import datetime

        return datetime.now(self.tz).date()
