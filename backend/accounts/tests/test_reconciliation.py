"""Tests for account reconciliation flow."""

import datetime
from zoneinfo import ZoneInfo

import pytest

from accounts.models import Account
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
        tx2 = TransactionFactory(
            user_id=user.id, account_id=account.id, is_verified=False
        )

        unverified = svc.get_unverified_transactions(str(account.id))
        assert len(unverified) == 1
        assert unverified[0]["id"] == str(tx2.id)

    def test_reconcile_marks_transactions_and_updates_account(self):
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        account = AccountFactory(user_id=user.id, institution_id=inst.id)
        svc = AccountService(str(user.id), ZoneInfo("UTC"))

        tx1 = TransactionFactory(
            user_id=user.id, account_id=account.id, is_verified=False
        )
        tx2 = TransactionFactory(
            user_id=user.id, account_id=account.id, is_verified=False
        )

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

        # Account 1: Never reconciled — make it old so the grace period doesn't suppress it
        acc1 = AccountFactory(
            user_id=user.id,
            institution_id=inst.id,
            name="Acc 1",
            last_reconciled_at=None,
        )
        old_created = datetime.datetime.now(ZoneInfo("UTC")) - datetime.timedelta(
            days=31
        )
        Account.objects.filter(id=acc1.id).update(created_at=old_created)

        # Account 2: Reconciled 31 days ago
        old_date = datetime.datetime.now(ZoneInfo("UTC")) - datetime.timedelta(days=31)
        acc2 = AccountFactory(
            user_id=user.id,
            institution_id=inst.id,
            name="Acc 2",
            last_reconciled_at=old_date,
        )

        # Account 3: Reconciled recently
        acc3 = AccountFactory(
            user_id=user.id,
            institution_id=inst.id,
            name="Acc 3",
            last_reconciled_at=datetime.datetime.now(ZoneInfo("UTC")),
        )

        from accounts.services import load_health_warnings

        raw = [
            svc.get_by_id(str(acc1.id)),
            svc.get_by_id(str(acc2.id)),
            svc.get_by_id(str(acc3.id)),
        ]
        summaries = [s for s in raw if s is not None]

        warnings = load_health_warnings(
            str(user.id), summaries, ZoneInfo("UTC"), include_stale_reconciliation=True
        )
        # Should have warnings for Acc 1 (missing) and Acc 2 (stale)
        warning_rules = [w.rule for w in warnings]
        assert "reconciliation_missing" in warning_rules
        assert "reconciliation_stale" in warning_rules
        # Account 1 & 2 only, Account 3 is fine
        assert len(warnings) == 2

    def test_new_account_no_reconciliation_warning(self):
        """Brand-new accounts (created < 30 days ago) must not show the reconciliation_missing banner."""
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        svc = AccountService(str(user.id), ZoneInfo("UTC"))

        # New account — created_at defaults to now (auto_now_add)
        acc = AccountFactory(
            user_id=user.id,
            institution_id=inst.id,
            name="New Account",
            last_reconciled_at=None,
        )

        from accounts.services import load_health_warnings

        summary = svc.get_by_id(str(acc.id))
        assert summary is not None

        warnings = load_health_warnings(
            str(user.id), [summary], ZoneInfo("UTC"), include_stale_reconciliation=True
        )
        warning_rules = [w.rule for w in warnings]
        assert "reconciliation_missing" not in warning_rules

    def test_old_account_shows_reconciliation_warning(self):
        """Accounts older than 30 days with no reconciliation must still show the banner."""
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        svc = AccountService(str(user.id), ZoneInfo("UTC"))

        acc = AccountFactory(
            user_id=user.id,
            institution_id=inst.id,
            name="Old Account",
            last_reconciled_at=None,
        )
        old_created = datetime.datetime.now(ZoneInfo("UTC")) - datetime.timedelta(
            days=45
        )
        Account.objects.filter(id=acc.id).update(created_at=old_created)

        from accounts.services import load_health_warnings

        summary = svc.get_by_id(str(acc.id))
        assert summary is not None

        # Create a transaction so it's not considered a "new" account with 0 tx
        from transactions.models import Transaction
        Transaction.objects.create(
            user_id=user.id,
            account_id=acc.id,
            amount=10,
            type="expense",
            date=datetime.date.today(),
        )

        warnings = load_health_warnings(
            str(user.id), [summary], ZoneInfo("UTC"), include_stale_reconciliation=True
        )
        warning_rules = [w.rule for w in warnings]
        assert "reconciliation_missing" in warning_rules

    def test_old_account_with_no_transactions_no_warning(self):
        """Accounts older than 30 days with NO transactions must NOT show the banner."""
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        svc = AccountService(str(user.id), ZoneInfo("UTC"))

        acc = AccountFactory(
            user_id=user.id,
            institution_id=inst.id,
            name="Old Empty Account",
            last_reconciled_at=None,
        )
        old_created = datetime.datetime.now(ZoneInfo("UTC")) - datetime.timedelta(
            days=45
        )
        Account.objects.filter(id=acc.id).update(created_at=old_created)

        from accounts.services import load_health_warnings

        summary = svc.get_by_id(str(acc.id))
        warnings = load_health_warnings(
            str(user.id), [summary], ZoneInfo("UTC"), include_stale_reconciliation=True
        )
        warning_rules = [w.rule for w in warnings]
        assert "reconciliation_missing" not in warning_rules
