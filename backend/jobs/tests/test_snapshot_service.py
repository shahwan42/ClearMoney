"""
Tests for SnapshotService — daily balance snapshot capture and backfill.

Uses real PostgreSQL. Creates users, accounts, transactions, and exchange rates
to test the full snapshot pipeline.
"""

from datetime import date, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.db import connection

from core.models import AccountSnapshot, DailySnapshot, ExchangeRateLog
from jobs.services.snapshot import SnapshotService
from tests.factories import (
    AccountFactory,
    InstitutionFactory,
    TransactionFactory,
    UserFactory,
    VirtualAccountFactory,
)

TZ = ZoneInfo("Africa/Cairo")


@pytest.mark.django_db(transaction=True)
class TestSnapshotService:
    """Tests for SnapshotService snapshot and backfill logic."""

    def setup_method(self) -> None:
        self.svc = SnapshotService(TZ)
        self.user = UserFactory()
        self.uid = self.user.id
        self.inst = InstitutionFactory(user_id=self.uid)

    def teardown_method(self) -> None:
        uid = str(self.uid)
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM account_snapshots WHERE user_id = %s", [uid])
            cursor.execute("DELETE FROM daily_snapshots WHERE user_id = %s", [uid])
            cursor.execute("DELETE FROM transactions WHERE user_id = %s", [uid])
            cursor.execute("DELETE FROM virtual_accounts WHERE user_id = %s", [uid])
            cursor.execute("DELETE FROM accounts WHERE user_id = %s", [uid])
            cursor.execute("DELETE FROM institutions WHERE user_id = %s", [uid])
        ExchangeRateLog.objects.filter(source="test-snapshot").delete()
        self.user.delete()

    def test_take_snapshot_basic_egp(self) -> None:
        """Single EGP account → correct net worth in daily snapshot."""
        AccountFactory(
            user_id=self.uid,
            institution_id=self.inst.id,
            currency="EGP",
            current_balance=5000,
            initial_balance=5000,
        )
        self.svc.take_snapshot(str(self.uid))

        snap = DailySnapshot.objects.filter(user_id=self.uid).first()
        assert snap is not None
        assert float(snap.net_worth_raw) == pytest.approx(5000, abs=0.01)

    def test_take_snapshot_with_usd_conversion(self) -> None:
        """EGP + USD accounts with exchange rate → correct net_worth_egp."""
        AccountFactory(
            user_id=self.uid,
            institution_id=self.inst.id,
            currency="EGP",
            current_balance=5000,
            initial_balance=5000,
        )
        AccountFactory(
            user_id=self.uid,
            institution_id=self.inst.id,
            currency="USD",
            current_balance=100,
            initial_balance=100,
        )
        # Seed exchange rate: 1 USD = 50 EGP
        ExchangeRateLog.objects.create(
            date=date.today(), rate=50.0, source="test-snapshot"
        )

        self.svc.take_snapshot(str(self.uid))

        snap = DailySnapshot.objects.filter(user_id=self.uid).first()
        assert snap is not None
        # net_worth_egp = (5100 - 100) + (100 * 50) = 5000 + 5000 = 10000
        assert float(snap.net_worth_egp) == pytest.approx(10000, abs=0.01)
        assert float(snap.exchange_rate) == pytest.approx(50.0, abs=0.01)

    def test_take_snapshot_excludes_virtual_accounts(self) -> None:
        """VA with exclude_from_net_worth=True reduces net_worth_raw."""
        AccountFactory(
            user_id=self.uid,
            institution_id=self.inst.id,
            currency="EGP",
            current_balance=5000,
            initial_balance=5000,
        )
        VirtualAccountFactory(
            user_id=self.uid,
            current_balance=1000,
            exclude_from_net_worth=True,
        )

        self.svc.take_snapshot(str(self.uid))

        snap = DailySnapshot.objects.filter(user_id=self.uid).first()
        assert snap is not None
        # 5000 - 1000 excluded = 4000
        assert float(snap.net_worth_raw) == pytest.approx(4000, abs=0.01)

    def test_upsert_idempotent(self) -> None:
        """Taking snapshot twice for same date → still one row (UPSERT)."""
        AccountFactory(
            user_id=self.uid,
            institution_id=self.inst.id,
            currency="EGP",
            current_balance=5000,
            initial_balance=5000,
        )
        self.svc.take_snapshot(str(self.uid))
        self.svc.take_snapshot(str(self.uid))

        count = DailySnapshot.objects.filter(user_id=self.uid).count()
        assert count == 1

    def test_account_snapshots_created(self) -> None:
        """Per-account snapshots are created alongside daily snapshot."""
        acc = AccountFactory(
            user_id=self.uid,
            institution_id=self.inst.id,
            currency="EGP",
            current_balance=3000,
            initial_balance=3000,
        )
        self.svc.take_snapshot(str(self.uid))

        acc_snap = AccountSnapshot.objects.filter(
            user_id=self.uid, account_id=acc.id
        ).first()
        assert acc_snap is not None
        assert float(acc_snap.balance) == pytest.approx(3000, abs=0.01)

    def test_backfill_creates_missing_days(self) -> None:
        """Backfill fills in missing days for the last N days."""
        AccountFactory(
            user_id=self.uid,
            institution_id=self.inst.id,
            currency="EGP",
            current_balance=1000,
            initial_balance=1000,
        )
        backfilled = self.svc.backfill_snapshots(str(self.uid), days=3)

        # Should have created snapshots for 4 days (3 days ago + 2 days ago + 1 day ago + today)
        count = DailySnapshot.objects.filter(user_id=self.uid).count()
        assert count == 4
        assert backfilled == 4

    def test_backfill_skips_existing(self) -> None:
        """Backfill does not overwrite existing snapshots (Exists check)."""
        AccountFactory(
            user_id=self.uid,
            institution_id=self.inst.id,
            currency="EGP",
            current_balance=1000,
            initial_balance=1000,
        )
        # Take today's snapshot first
        self.svc.take_snapshot(str(self.uid))

        # Now backfill — today should be skipped
        backfilled = self.svc.backfill_snapshots(str(self.uid), days=2)
        # Only 2 days backfilled (yesterday + 2 days ago), today already exists
        assert backfilled == 2

    def test_backfill_historical_balance(self) -> None:
        """Historical balance = current_balance - future deltas."""
        acc = AccountFactory(
            user_id=self.uid,
            institution_id=self.inst.id,
            currency="EGP",
            current_balance=1000,
            initial_balance=800,
        )
        # Transaction 1 day ago: +200 income
        yesterday = date.today() - timedelta(days=1)
        TransactionFactory(
            user_id=self.uid,
            account_id=acc.id,
            type="income",
            amount=200,
            balance_delta=200,
            date=yesterday,
        )

        # Backfill 3 days
        self.svc.backfill_snapshots(str(self.uid), days=3)

        # 3 days ago: current(1000) - future_deltas(200) = 800
        three_days_ago = date.today() - timedelta(days=3)
        snap = DailySnapshot.objects.filter(
            user_id=self.uid, date=three_days_ago
        ).first()
        assert snap is not None
        assert float(snap.net_worth_raw) == pytest.approx(800, abs=0.01)

    def test_daily_spending_and_income(self) -> None:
        """Snapshot captures daily spending and income totals."""
        acc = AccountFactory(
            user_id=self.uid,
            institution_id=self.inst.id,
            currency="EGP",
            current_balance=5000,
            initial_balance=5000,
        )
        today = date.today()
        TransactionFactory(
            user_id=self.uid,
            account_id=acc.id,
            type="expense",
            amount=150,
            balance_delta=-150,
            date=today,
        )
        TransactionFactory(
            user_id=self.uid,
            account_id=acc.id,
            type="income",
            amount=300,
            balance_delta=300,
            date=today,
        )

        self.svc.take_snapshot(str(self.uid))

        snap = DailySnapshot.objects.filter(user_id=self.uid).first()
        assert snap is not None
        assert float(snap.daily_spending) == pytest.approx(150, abs=0.01)
        assert float(snap.daily_income) == pytest.approx(300, abs=0.01)
