"""Tests for account reconciliation flow."""

import datetime
from zoneinfo import ZoneInfo

import pytest

from accounts.services import AccountService
from tests.factories import (
    AccountFactory,
    InstitutionFactory,
    TransactionFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestAccountReconciliation:
    def test_get_unverified_transactions(self):
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        account = AccountFactory(user_id=user.id, institution_id=inst.id)
        svc = AccountService(str(user.id), ZoneInfo("UTC"))

        # Verified tx
        TransactionFactory(user_id=user.id, account_id=account.id, is_verified=True)
        # Unverified tx
        tx2 = TransactionFactory(user_id=user.id, account_id=account.id, is_verified=False)

        unverified = svc.get_unverified_transactions(str(account.id))
        assert len(unverified) == 1
        assert unverified[0]["id"] == str(tx2.id)

    def test_reconcile_marks_transactions_and_updates_account(self):
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        account = AccountFactory(user_id=user.id, institution_id=inst.id)
        svc = AccountService(str(user.id), ZoneInfo("UTC"))

        tx1 = TransactionFactory(user_id=user.id, account_id=account.id, is_verified=False)
        tx2 = TransactionFactory(user_id=user.id, account_id=account.id, is_verified=False)

        svc.reconcile(str(account.id), [str(tx1.id)])

        tx1.refresh_from_db()
        tx2.refresh_from_db()
        account.refresh_from_db()

        assert tx1.is_verified is True
        assert tx2.is_verified is False
        assert account.last_reconciled_at is not None

    def test_health_warnings_for_stale_reconciliation(self):
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        svc = AccountService(str(user.id), ZoneInfo("UTC"))

        # Account 1: Never reconciled
        acc1 = AccountFactory(user_id=user.id, institution_id=inst.id, name="Acc 1", last_reconciled_at=None)

        # Account 2: Reconciled 31 days ago
        old_date = datetime.datetime.now(ZoneInfo("UTC")) - datetime.timedelta(days=31)
        acc2 = AccountFactory(user_id=user.id, institution_id=inst.id, name="Acc 2", last_reconciled_at=old_date)

        # Account 3: Reconciled recently
        acc3 = AccountFactory(user_id=user.id, institution_id=inst.id, name="Acc 3", last_reconciled_at=datetime.datetime.now(ZoneInfo("UTC")))

        from accounts.services import load_health_warnings
        summaries = [
            svc.get_by_id(str(acc1.id)),
            svc.get_by_id(str(acc2.id)),
            svc.get_by_id(str(acc3.id)),
        ]

        warnings = load_health_warnings(str(user.id), summaries, ZoneInfo("UTC"), include_stale_reconciliation=True)
        # Should have warnings for Acc 1 (missing) and Acc 2 (stale)
        warning_rules = [w.rule for w in warnings]
        assert "reconciliation_missing" in warning_rules
        assert "reconciliation_stale" in warning_rules
        # Account 1 & 2 only, Account 3 is fine
        assert len(warnings) == 2
