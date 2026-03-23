"""Tests for model methods defined in core/models.py."""

from decimal import Decimal

import pytest

from tests.factories import (
    AccountFactory,
    InstitutionFactory,
    InvestmentFactory,
    UserFactory,
    VirtualAccountFactory,
)


@pytest.mark.django_db
class TestAccountIsCreditType:
    """Account.is_credit_type() -> bool"""

    def test_credit_card_is_credit_type(self) -> None:
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        account = AccountFactory(
            user_id=user.id, institution_id=inst.id, type="credit_card"
        )
        assert account.is_credit_type() is True

    def test_credit_limit_is_credit_type(self) -> None:
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        account = AccountFactory(
            user_id=user.id, institution_id=inst.id, type="credit_limit"
        )
        assert account.is_credit_type() is True

    def test_savings_is_not_credit_type(self) -> None:
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        account = AccountFactory(
            user_id=user.id, institution_id=inst.id, type="savings"
        )
        assert account.is_credit_type() is False

    def test_current_is_not_credit_type(self) -> None:
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        account = AccountFactory(
            user_id=user.id, institution_id=inst.id, type="current"
        )
        assert account.is_credit_type() is False


@pytest.mark.django_db
class TestVirtualAccountProgressPct:
    """VirtualAccount.progress_pct() -> float"""

    def test_zero_balance(self) -> None:
        user = UserFactory()
        va = VirtualAccountFactory(
            user_id=user.id,
            current_balance=Decimal("0"),
            target_amount=Decimal("1000"),
        )
        assert va.progress_pct() == 0.0

    def test_half_progress(self) -> None:
        user = UserFactory()
        va = VirtualAccountFactory(
            user_id=user.id,
            current_balance=Decimal("500"),
            target_amount=Decimal("1000"),
        )
        assert va.progress_pct() == 50.0

    def test_full_progress(self) -> None:
        user = UserFactory()
        va = VirtualAccountFactory(
            user_id=user.id,
            current_balance=Decimal("1000"),
            target_amount=Decimal("1000"),
        )
        assert va.progress_pct() == 100.0

    def test_no_target_returns_zero(self) -> None:
        user = UserFactory()
        va = VirtualAccountFactory(
            user_id=user.id,
            current_balance=Decimal("500"),
            target_amount=None,
        )
        assert va.progress_pct() == 0.0


@pytest.mark.django_db
class TestInvestmentValuation:
    """Investment.valuation() -> float"""

    def test_basic_valuation(self) -> None:
        user = UserFactory()
        inv = InvestmentFactory(
            user_id=user.id,
            units=Decimal("10.0"),
            last_unit_price=Decimal("50.0"),
        )
        assert inv.valuation() == 500.0

    def test_zero_units(self) -> None:
        user = UserFactory()
        inv = InvestmentFactory(
            user_id=user.id,
            units=Decimal("0"),
            last_unit_price=Decimal("50.0"),
        )
        assert inv.valuation() == 0.0
