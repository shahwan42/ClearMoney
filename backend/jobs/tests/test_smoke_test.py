from __future__ import annotations

from io import StringIO

import pytest

from accounts.models import Account, Institution
from auth_app.models import AuthToken, Session, User
from budgets.models import Budget, TotalBudget
from categories.models import Category
from jobs.management.commands.deploy_smoke_test import (
    SMOKE_EMAIL,
    SMOKE_ISOLATION_EMAIL,
    _cleanup,
)
from tests.factories import AuthTokenFactory, BudgetFactory, SessionFactory, UserFactory
from transactions.models import Tag, Transaction


@pytest.mark.django_db(transaction=True)
class TestSmokeCleanup:
    def test_cleanup_when_no_smoke_user_exists_is_noop(self) -> None:
        out = StringIO()

        _cleanup(out)

        assert "nothing to clean" in out.getvalue().lower()

    def test_cleanup_deletes_all_smoke_data(self) -> None:
        smoke_user = UserFactory(email=SMOKE_EMAIL)
        other_smoke_user = UserFactory(email=SMOKE_ISOLATION_EMAIL)
        keep_user = UserFactory()

        category = Category.objects.create(
            user_id=smoke_user.id,
            name={"en": "Smoke Category"},
            type="expense",
        )
        institution = Institution.objects.create(
            user_id=smoke_user.id,
            name="[SMOKE] Bank",
            type="bank",
        )
        account = Account.objects.create(
            user_id=smoke_user.id,
            institution=institution,
            name="[SMOKE] Account",
            type="current",
            currency="EGP",
            current_balance="1000.00",
            initial_balance="1000.00",
        )
        Transaction.objects.create(
            user_id=smoke_user.id,
            account=account,
            category=category,
            type="expense",
            amount="50.00",
            currency="EGP",
            balance_delta="-50.00",
        )
        BudgetFactory(user_id=smoke_user.id, category_id=category.id)
        TotalBudget.objects.create(
            user_id=smoke_user.id,
            monthly_limit="5000.00",
            currency="EGP",
        )
        Tag.objects.create(user_id=smoke_user.id, name="[SMOKE]", color="#64748b")
        SessionFactory(user=smoke_user)
        AuthTokenFactory(email=SMOKE_EMAIL)
        AuthTokenFactory(email=SMOKE_ISOLATION_EMAIL)

        other_inst = Institution.objects.create(
            user_id=other_smoke_user.id,
            name="[SMOKE] Isolation Bank",
            type="bank",
        )
        Account.objects.create(
            user_id=other_smoke_user.id,
            institution=other_inst,
            name="[SMOKE] Isolation Account",
            type="current",
            currency="EGP",
            current_balance="10.00",
            initial_balance="10.00",
        )

        keep_category = Category.objects.create(
            user_id=keep_user.id,
            name={"en": "Keep"},
            type="expense",
        )
        keep_inst = Institution.objects.create(
            user_id=keep_user.id,
            name="Keep Bank",
            type="bank",
        )
        keep_account = Account.objects.create(
            user_id=keep_user.id,
            institution=keep_inst,
            name="Keep Account",
            type="current",
            currency="EGP",
            current_balance="100.00",
            initial_balance="100.00",
        )
        Transaction.objects.create(
            user_id=keep_user.id,
            account=keep_account,
            category=keep_category,
            type="expense",
            amount="10.00",
            currency="EGP",
            balance_delta="-10.00",
        )

        out = StringIO()

        _cleanup(out)

        assert not User.objects.filter(email=SMOKE_EMAIL).exists()
        assert not User.objects.filter(email=SMOKE_ISOLATION_EMAIL).exists()
        assert not AuthToken.objects.filter(
            email__in=[SMOKE_EMAIL, SMOKE_ISOLATION_EMAIL]
        ).exists()
        assert not Session.objects.filter(user_id=smoke_user.id).exists()
        assert not Institution.objects.filter(user_id=smoke_user.id).exists()
        assert not Account.objects.filter(user_id=smoke_user.id).exists()
        assert not Transaction.objects.filter(user_id=smoke_user.id).exists()
        assert not Budget.objects.filter(user_id=smoke_user.id).exists()
        assert not TotalBudget.objects.filter(user_id=smoke_user.id).exists()
        assert not Category.objects.filter(user_id=smoke_user.id).exists()
        assert not Tag.objects.filter(user_id=smoke_user.id).exists()

        assert User.objects.filter(id=keep_user.id).exists()
        assert Account.objects.filter(user_id=keep_user.id).exists()
        assert Transaction.objects.filter(user_id=keep_user.id).exists()
        assert "Smoke cleanup complete" in out.getvalue()

    def test_sentinel_email_constant_matches_expected_value(self) -> None:
        assert SMOKE_EMAIL == "smoke-deploy@clearmoney.app"
