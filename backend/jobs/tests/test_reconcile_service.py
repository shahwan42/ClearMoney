"""
Tests for ReconcileService — balance verification and auto-fix.

Creates accounts + transactions to test reconciliation.
"""

import pytest

from jobs.services.reconcile import ReconcileService
from tests.factories import (
    AccountFactory,
    InstitutionFactory,
    TransactionFactory,
    UserFactory,
)


@pytest.mark.django_db(transaction=True)
class TestReconcileService:
    """Tests for ReconcileService.reconcile()."""

    def setup_method(self) -> None:
        self.svc = ReconcileService()
        self.user = UserFactory()
        self.uid = self.user.id
        self.inst = InstitutionFactory(user_id=self.uid)

    def test_no_discrepancies_when_balanced(self) -> None:
        """Account with matching current_balance returns no discrepancies."""
        account = AccountFactory(
            user_id=self.uid,
            institution_id=self.inst.id,
            initial_balance=1000,
            current_balance=800,
        )
        TransactionFactory(
            user_id=self.uid,
            account_id=account.id,
            type="expense",
            amount=200,
            balance_delta=-200,
        )
        discrepancies = self.svc.reconcile()
        account_ids = [d.account_id for d in discrepancies]
        assert str(account.id) not in account_ids

    def test_detects_discrepancy(self) -> None:
        """Wrong current_balance is detected as a discrepancy."""
        account = AccountFactory(
            user_id=self.uid,
            institution_id=self.inst.id,
            initial_balance=1000,
            current_balance=900,  # wrong — should be 800
        )
        TransactionFactory(
            user_id=self.uid,
            account_id=account.id,
            type="expense",
            amount=200,
            balance_delta=-200,
        )
        discrepancies = self.svc.reconcile()
        match = [d for d in discrepancies if d.account_id == str(account.id)]
        assert len(match) == 1
        assert match[0].cached_balance == 900
        assert match[0].expected_balance == 800
        assert abs(match[0].difference - (-100)) < 0.01

    def test_auto_fix_updates_balance(self) -> None:
        """auto_fix=True corrects current_balance to match computed value."""
        account = AccountFactory(
            user_id=self.uid,
            institution_id=self.inst.id,
            initial_balance=1000,
            current_balance=900,  # wrong
        )
        TransactionFactory(
            user_id=self.uid,
            account_id=account.id,
            type="expense",
            amount=200,
            balance_delta=-200,
        )
        self.svc.reconcile(auto_fix=True)

        # Verify the fix
        account.refresh_from_db()
        assert float(account.current_balance) == pytest.approx(800, abs=0.01)

    def test_tolerance_ignores_small_diffs(self) -> None:
        """Differences below 0.005 are ignored (floating-point noise)."""
        AccountFactory(
            user_id=self.uid,
            institution_id=self.inst.id,
            initial_balance=1000,
            current_balance=1000.003,  # within tolerance
        )
        discrepancies = self.svc.reconcile()
        # Should not be flagged
        our_accounts = [d for d in discrepancies if d.cached_balance == 1000.003]
        assert len(our_accounts) == 0

    def test_empty_account_no_transactions(self) -> None:
        """Account with zero transactions reconciles cleanly (COALESCE handles NULL)."""
        account = AccountFactory(
            user_id=self.uid,
            institution_id=self.inst.id,
            initial_balance=500,
            current_balance=500,
        )
        discrepancies = self.svc.reconcile()
        account_ids = [d.account_id for d in discrepancies]
        assert str(account.id) not in account_ids
