"""
Integration tests for management commands — verify they run without error.

Uses call_command() to execute each command and checks stdout output.
"""

import logging
from datetime import date, timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from pytest_mock import MockerFixture

from auth_app.models import DailySnapshot
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


@pytest.mark.django_db(transaction=True)
class TestStartupJobsPartialFailure:
    """Verify partial failure resilience in run_startup_jobs."""

    def test_single_job_failure_does_not_stop_others(
        self, mocker: MockerFixture, caplog: pytest.LogCaptureFixture
    ) -> None:
        """One failing sub-command should not prevent the rest from running."""  # gap: functional
        # Make reconcile_balances blow up
        original_call_command = call_command

        calls: list[str] = []

        def tracking_call_command(name: str, **kwargs: object) -> None:
            calls.append(name)
            if name == "reconcile_balances":
                raise RuntimeError("simulated reconcile failure")
            original_call_command(name, **kwargs)

        mocker.patch(
            "jobs.management.commands.run_startup_jobs.call_command",
            side_effect=tracking_call_command,
        )

        out = StringIO()
        with caplog.at_level(logging.INFO):
            call_command("run_startup_jobs", stdout=out)

        # All 5 jobs were attempted despite reconcile_balances failing
        assert "cleanup_sessions" in calls
        assert "process_recurring" in calls
        assert "reconcile_balances" in calls
        assert "refresh_views" in calls
        assert "take_snapshots" in calls

        # The orchestrator still completed
        assert "startup_job.all_complete" in caplog.text
