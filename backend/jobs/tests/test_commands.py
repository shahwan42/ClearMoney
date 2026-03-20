"""
Integration tests for management commands — verify they run without error.

Uses call_command() to execute each command and checks stdout output.
"""

import logging
from datetime import date, timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.db import connection

from core.models import DailySnapshot
from tests.factories import (
    AccountFactory,
    InstitutionFactory,
    RecurringRuleFactory,
    UserFactory,
)


@pytest.mark.django_db(transaction=True)
class TestCommands:
    """Integration tests for all jobs management commands."""

    def setup_method(self) -> None:
        self.user = UserFactory()
        self.uid = self.user.id
        self.inst = InstitutionFactory(user_id=self.uid)
        self.out = StringIO()

    def teardown_method(self) -> None:
        uid = str(self.uid)
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM account_snapshots WHERE user_id = %s", [uid])
            cursor.execute("DELETE FROM daily_snapshots WHERE user_id = %s", [uid])
            cursor.execute("DELETE FROM transactions WHERE user_id = %s", [uid])
            cursor.execute("DELETE FROM recurring_rules WHERE user_id = %s", [uid])
            cursor.execute("DELETE FROM accounts WHERE user_id = %s", [uid])
            cursor.execute("DELETE FROM institutions WHERE user_id = %s", [uid])
        self.user.delete()

    def test_cleanup_sessions_command(self) -> None:
        """cleanup_sessions runs without error."""
        call_command("cleanup_sessions", stdout=self.out)
        assert "Cleanup complete" in self.out.getvalue()

    def test_reconcile_balances_command(self) -> None:
        """reconcile_balances runs and reports results."""
        AccountFactory(
            user_id=self.uid,
            institution_id=self.inst.id,
            initial_balance=1000,
            current_balance=1000,
        )
        call_command("reconcile_balances", stdout=self.out)
        assert (
            "balances match" in self.out.getvalue().lower()
            or "discrepancy" in self.out.getvalue().lower()
        )

    def test_reconcile_fix_flag(self) -> None:
        """--fix flag is accepted and works."""
        AccountFactory(
            user_id=self.uid,
            institution_id=self.inst.id,
            initial_balance=1000,
            current_balance=1000,
        )
        call_command("reconcile_balances", "--fix", stdout=self.out)
        output = self.out.getvalue()
        assert "match" in output.lower() or "fixed" in output.lower()

    def test_refresh_views_command(self) -> None:
        """refresh_views runs without error."""
        call_command("refresh_views", stdout=self.out)
        assert "refreshed" in self.out.getvalue().lower()

    def test_take_snapshots_command(self) -> None:
        """take_snapshots creates snapshot rows."""
        AccountFactory(
            user_id=self.uid,
            institution_id=self.inst.id,
            currency="EGP",
            current_balance=1000,
            initial_balance=1000,
        )
        call_command("take_snapshots", "--days", "3", stdout=self.out)
        assert "complete" in self.out.getvalue().lower()
        assert DailySnapshot.objects.filter(user_id=self.uid).exists()

    def test_take_snapshots_days_flag(self) -> None:
        """--days flag controls backfill range."""
        AccountFactory(
            user_id=self.uid,
            institution_id=self.inst.id,
            currency="EGP",
            current_balance=1000,
            initial_balance=1000,
        )
        call_command("take_snapshots", "--days", "2", stdout=self.out)
        # Should have 3 snapshots: today + 2 backfilled days
        count = DailySnapshot.objects.filter(user_id=self.uid).count()
        assert count == 3

    def test_process_recurring_command(self) -> None:
        """process_recurring runs without error."""
        # Create an auto-confirm rule that's due today
        acc = AccountFactory(
            user_id=self.uid,
            institution_id=self.inst.id,
            currency="EGP",
            current_balance=5000,
            initial_balance=5000,
        )
        RecurringRuleFactory(
            user_id=self.uid,
            auto_confirm=True,
            next_due_date=date.today() - timedelta(days=1),
            template_transaction={
                "type": "expense",
                "amount": 100,
                "currency": "EGP",
                "account_id": str(acc.id),
            },
        )
        call_command("process_recurring", stdout=self.out)
        assert "complete" in self.out.getvalue().lower()

    def test_run_startup_jobs_command(self, caplog: pytest.LogCaptureFixture) -> None:
        """run_startup_jobs orchestrates all sub-commands."""
        AccountFactory(
            user_id=self.uid,
            institution_id=self.inst.id,
            currency="EGP",
            current_balance=1000,
            initial_balance=1000,
        )
        with caplog.at_level(logging.INFO):
            call_command("run_startup_jobs", stdout=self.out)
        assert "startup_job.all_complete" in caplog.text
