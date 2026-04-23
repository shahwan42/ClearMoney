"""
Tests for SnapshotService — daily balance snapshot capture and backfill.

Creates users, accounts, transactions, and exchange rates to test the
full snapshot pipeline.
"""

from datetime import date, timedelta
from zoneinfo import ZoneInfo

import pytest

from accounts.models import AccountSnapshot
from auth_app.models import DailySnapshot, HistoricalSnapshot
from exchange_rates.models import ExchangeRateLog
from jobs.services.snapshot import SnapshotService
from tests.factories import (
    AccountFactory,
    AccountSnapshotFactory,
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

    def test_take_snapshot_basic_egp(self) -> None:
        """Single EGP account writes canonical and legacy history."""
        AccountFactory(
            user_id=self.uid,
            institution_id=self.inst.id,
            currency="EGP",
            current_balance=5000,
            initial_balance=5000,
        )

        self.svc.take_snapshot(str(self.uid))

        snap = DailySnapshot.objects.filter(user_id=self.uid).first()
        hist = HistoricalSnapshot.objects.filter(
            user_id=self.uid, currency="EGP"
        ).first()
        assert snap is not None
        assert hist is not None
        assert float(snap.net_worth_raw) == pytest.approx(5000, abs=0.01)
        assert float(hist.net_worth) == pytest.approx(5000, abs=0.01)

    def test_take_snapshot_with_usd_conversion(self) -> None:
        """Exact USD rows are preserved while legacy EGP projection still works."""
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
        ExchangeRateLog.objects.create(
            date=date.today(), rate=50.0, source="test-snapshot"
        )

        self.svc.take_snapshot(str(self.uid))

        snap = DailySnapshot.objects.filter(user_id=self.uid).first()
        usd_hist = HistoricalSnapshot.objects.filter(
            user_id=self.uid, currency="USD"
        ).first()
        assert snap is not None
        assert usd_hist is not None
        assert float(snap.net_worth_egp) == pytest.approx(10000, abs=0.01)
        assert float(snap.exchange_rate) == pytest.approx(50.0, abs=0.01)
        assert float(usd_hist.net_worth) == pytest.approx(100, abs=0.01)

    def test_take_snapshot_excludes_virtual_accounts(self) -> None:
        """Excluded virtual account balance reduces EGP history and legacy totals."""
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
        hist = HistoricalSnapshot.objects.filter(
            user_id=self.uid, currency="EGP"
        ).first()
        assert snap is not None
        assert hist is not None
        assert float(snap.net_worth_raw) == pytest.approx(4000, abs=0.01)
        assert float(hist.net_worth) == pytest.approx(4000, abs=0.01)

    def test_upsert_idempotent(self) -> None:
        """Taking snapshot twice for same date does not duplicate rows."""
        AccountFactory(
            user_id=self.uid,
            institution_id=self.inst.id,
            currency="EGP",
            current_balance=5000,
            initial_balance=5000,
        )

        self.svc.take_snapshot(str(self.uid))
        self.svc.take_snapshot(str(self.uid))

        assert DailySnapshot.objects.filter(user_id=self.uid).count() == 1
        assert HistoricalSnapshot.objects.filter(user_id=self.uid).count() == 1

    def test_account_snapshots_created(self) -> None:
        """Per-account snapshots are created alongside historical totals."""
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

        assert DailySnapshot.objects.filter(user_id=self.uid).count() == 4
        assert HistoricalSnapshot.objects.filter(user_id=self.uid).count() == 4
        assert backfilled == 4

    def test_backfill_skips_existing(self) -> None:
        """Backfill only counts dates missing canonical history."""
        AccountFactory(
            user_id=self.uid,
            institution_id=self.inst.id,
            currency="EGP",
            current_balance=1000,
            initial_balance=1000,
        )

        self.svc.take_snapshot(str(self.uid))

        backfilled = self.svc.backfill_snapshots(str(self.uid), days=2)
        assert backfilled == 2

    def test_backfill_rerun_is_idempotent(self) -> None:
        """Rerunning backfill updates safely without duplicating history."""
        AccountFactory(
            user_id=self.uid,
            institution_id=self.inst.id,
            currency="EGP",
            current_balance=1000,
            initial_balance=1000,
        )

        first = self.svc.backfill_snapshots(str(self.uid), days=2)
        second = self.svc.backfill_snapshots(str(self.uid), days=2)

        assert first == 3
        assert second == 0
        assert HistoricalSnapshot.objects.filter(user_id=self.uid).count() == 3

    def test_backfill_historical_balance(self) -> None:
        """Historical balance = current_balance - future deltas."""
        acc = AccountFactory(
            user_id=self.uid,
            institution_id=self.inst.id,
            currency="EGP",
            current_balance=1000,
            initial_balance=800,
        )
        yesterday = date.today() - timedelta(days=1)
        TransactionFactory(
            user_id=self.uid,
            account_id=acc.id,
            type="income",
            amount=200,
            balance_delta=200,
            date=yesterday,
        )

        self.svc.backfill_snapshots(str(self.uid), days=3)

        three_days_ago = date.today() - timedelta(days=3)
        snap = DailySnapshot.objects.filter(
            user_id=self.uid, date=three_days_ago
        ).first()
        hist = HistoricalSnapshot.objects.filter(
            user_id=self.uid, date=three_days_ago, currency="EGP"
        ).first()
        assert snap is not None
        assert hist is not None
        assert float(snap.net_worth_raw) == pytest.approx(800, abs=0.01)
        assert float(hist.net_worth) == pytest.approx(800, abs=0.01)

    def test_dormant_account_excluded_from_snapshot(self) -> None:
        """Dormant account balance is not included in net_worth_raw."""  # gap: functional
        AccountFactory(
            user_id=self.uid,
            institution_id=self.inst.id,
            currency="EGP",
            current_balance=5000,
            initial_balance=5000,
            is_dormant=False,
        )
        AccountFactory(
            user_id=self.uid,
            institution_id=self.inst.id,
            currency="EGP",
            current_balance=9999,
            initial_balance=9999,
            is_dormant=True,
        )

        self.svc.take_snapshot(str(self.uid))

        snap = DailySnapshot.objects.filter(user_id=self.uid).first()
        hist = HistoricalSnapshot.objects.filter(
            user_id=self.uid, currency="EGP"
        ).first()
        assert snap is not None
        assert hist is not None
        assert float(snap.net_worth_raw) == pytest.approx(5000, abs=0.01)
        assert float(hist.net_worth) == pytest.approx(5000, abs=0.01)

    def test_daily_spending_and_income(self) -> None:
        """Snapshot captures daily spending and income totals per currency."""
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
        hist = HistoricalSnapshot.objects.filter(
            user_id=self.uid, currency="EGP"
        ).first()
        assert snap is not None
        assert hist is not None
        assert float(snap.daily_spending) == pytest.approx(150, abs=0.01)
        assert float(snap.daily_income) == pytest.approx(300, abs=0.01)
        assert float(hist.daily_spending) == pytest.approx(150, abs=0.01)
        assert float(hist.daily_income) == pytest.approx(300, abs=0.01)

    def test_supports_third_currency_history(self) -> None:
        """Snapshots store third-currency history exactly."""
        AccountFactory(
            user_id=self.uid,
            institution_id=self.inst.id,
            currency="EUR",
            current_balance=250,
            initial_balance=250,
        )

        self.svc.take_snapshot(str(self.uid))

        hist = HistoricalSnapshot.objects.get(user_id=self.uid, currency="EUR")
        assert float(hist.net_worth) == pytest.approx(250, abs=0.01)

    def test_backfill_historical_snapshots_from_account_snapshots(self) -> None:
        """Canonical history can be rebuilt from account snapshot history."""
        egp = AccountFactory(
            user_id=self.uid,
            institution_id=self.inst.id,
            currency="EGP",
            current_balance=2000,
            initial_balance=2000,
        )
        usd = AccountFactory(
            user_id=self.uid,
            institution_id=self.inst.id,
            currency="USD",
            current_balance=40,
            initial_balance=40,
        )
        two_days_ago = date.today() - timedelta(days=2)

        AccountSnapshotFactory(
            user_id=self.uid,
            account=egp,
            date=two_days_ago,
            balance=1500,
        )
        AccountSnapshotFactory(
            user_id=self.uid,
            account=usd,
            date=two_days_ago,
            balance=25,
        )

        rebuilt = self.svc.backfill_historical_snapshots_from_account_snapshots(
            str(self.uid)
        )

        egp_hist = HistoricalSnapshot.objects.get(
            user_id=self.uid, date=two_days_ago, currency="EGP"
        )
        usd_hist = HistoricalSnapshot.objects.get(
            user_id=self.uid, date=two_days_ago, currency="USD"
        )
        assert rebuilt >= 1
        assert float(egp_hist.net_worth) == pytest.approx(1500, abs=0.01)
        assert float(usd_hist.net_worth) == pytest.approx(25, abs=0.01)
