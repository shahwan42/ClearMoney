"""Tests for account balance check flow and reminders."""

import datetime
from zoneinfo import ZoneInfo

import pytest

from accounts.models import Account
from accounts.services import AccountService
from tests.factories import AccountFactory, InstitutionFactory, UserFactory


@pytest.mark.django_db
class TestAccountBalanceCheck:
    def test_record_balance_check_saves_entered_balance_and_status(self) -> None:
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        account = AccountFactory(
            user_id=user.id,
            institution_id=inst.id,
            current_balance=1000,
        )
        svc = AccountService(str(user.id), ZoneInfo("UTC"))

        result = svc.record_balance_check(str(account.id), 1000)

        account.refresh_from_db()
        assert result["status"] == "matched"
        assert result["difference"] == pytest.approx(0.0)
        assert account.last_balance_check_at is not None
        assert float(account.last_checked_balance) == pytest.approx(1000.0)
        assert float(account.last_balance_check_diff) == pytest.approx(0.0)
        assert account.last_balance_check_status == "matched"

    def test_create_balance_correction_writes_explicit_transaction(self) -> None:
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        account = AccountFactory(
            user_id=user.id,
            institution_id=inst.id,
            current_balance=1000,
        )
        svc = AccountService(str(user.id), ZoneInfo("UTC"))

        tx_id = svc.create_balance_correction(str(account.id), 850)

        from transactions.models import Transaction

        account.refresh_from_db()
        tx = Transaction.objects.get(id=tx_id)
        assert tx.note == "Balance correction"
        assert tx.type == "expense"
        assert float(tx.amount) == pytest.approx(150.0)
        assert float(tx.balance_delta) == pytest.approx(-150.0)
        assert float(account.current_balance) == pytest.approx(850.0)
        assert account.last_balance_check_status == "matched"
        assert float(account.last_balance_check_diff) == pytest.approx(0.0)

    def test_health_warnings_for_missing_and_stale_balance_checks(self) -> None:
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        svc = AccountService(str(user.id), ZoneInfo("UTC"))

        acc1 = AccountFactory(
            user_id=user.id,
            institution_id=inst.id,
            name="Acc 1",
            last_balance_check_at=None,
        )
        old_created = datetime.datetime.now(ZoneInfo("UTC")) - datetime.timedelta(
            days=31
        )
        Account.objects.filter(id=acc1.id).update(created_at=old_created)

        from transactions.models import Transaction

        Transaction.objects.create(
            user_id=user.id,
            account_id=acc1.id,
            amount=10,
            currency="EGP",
            type="expense",
            balance_delta=-10,
            date=datetime.date.today(),
        )

        old_date = datetime.datetime.now(ZoneInfo("UTC")) - datetime.timedelta(days=31)
        acc2 = AccountFactory(
            user_id=user.id,
            institution_id=inst.id,
            name="Acc 2",
            last_balance_check_at=old_date,
        )

        acc3 = AccountFactory(
            user_id=user.id,
            institution_id=inst.id,
            name="Acc 3",
            last_balance_check_at=datetime.datetime.now(ZoneInfo("UTC")),
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
        warning_rules = [w.rule for w in warnings]
        assert "balance_check_missing" in warning_rules
        assert "balance_check_stale" in warning_rules
        assert len(warnings) == 2

    def test_new_account_no_balance_check_warning(self) -> None:
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        svc = AccountService(str(user.id), ZoneInfo("UTC"))

        acc = AccountFactory(
            user_id=user.id,
            institution_id=inst.id,
            name="New Account",
            last_balance_check_at=None,
        )

        from accounts.services import load_health_warnings

        summary = svc.get_by_id(str(acc.id))
        assert summary is not None

        warnings = load_health_warnings(
            str(user.id), [summary], ZoneInfo("UTC"), include_stale_reconciliation=True
        )
        warning_rules = [w.rule for w in warnings]
        assert "balance_check_missing" not in warning_rules

    def test_old_account_with_no_transactions_no_warning(self) -> None:
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        svc = AccountService(str(user.id), ZoneInfo("UTC"))

        acc = AccountFactory(
            user_id=user.id,
            institution_id=inst.id,
            name="Old Empty Account",
            last_balance_check_at=None,
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
        assert "balance_check_missing" not in warning_rules
