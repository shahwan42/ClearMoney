"""Tests for FeePreset model and compute_fee helper."""

from decimal import Decimal

import pytest
from django.db import IntegrityError

from fee_presets.models import FeePreset, compute_fee
from tests.factories import UserFactory


@pytest.mark.django_db
class TestFeePresetModel:
    def test_create_flat_preset(self):
        user = UserFactory()
        p = FeePreset.objects.create(
            user_id=user.id,
            name="ATM",
            currency="EGP",
            calc_type="flat",
            value=Decimal("5.00"),
        )
        assert p.id is not None
        assert p.name == "ATM"
        assert p.calc_type == "flat"
        assert p.archived is False

    def test_create_percent_preset_with_clamps(self):
        user = UserFactory()
        p = FeePreset.objects.create(
            user_id=user.id,
            name="InstaPay",
            currency="EGP",
            calc_type="percent",
            value=Decimal("0.001"),
            min_fee=Decimal("0.50"),
            max_fee=Decimal("20.00"),
        )
        assert p.min_fee == Decimal("0.50")
        assert p.max_fee == Decimal("20.00")

    def test_unique_per_user_name_currency(self):
        user = UserFactory()
        FeePreset.objects.create(
            user_id=user.id,
            name="ATM",
            currency="EGP",
            calc_type="flat",
            value=Decimal("5"),
        )
        with pytest.raises(IntegrityError):
            FeePreset.objects.create(
                user_id=user.id,
                name="ATM",
                currency="EGP",
                calc_type="flat",
                value=Decimal("10"),
            )

    def test_same_name_different_currency_allowed(self):
        user = UserFactory()
        FeePreset.objects.create(
            user_id=user.id,
            name="ATM",
            currency="EGP",
            calc_type="flat",
            value=Decimal("5"),
        )
        FeePreset.objects.create(
            user_id=user.id,
            name="ATM",
            currency="USD",
            calc_type="flat",
            value=Decimal("2"),
        )

    def test_user_scoped_isolation(self):
        a = UserFactory()
        b = UserFactory()
        FeePreset.objects.create(
            user_id=a.id,
            name="ATM",
            currency="EGP",
            calc_type="flat",
            value=Decimal("5"),
        )
        assert FeePreset.objects.for_user(str(a.id)).count() == 1
        assert FeePreset.objects.for_user(str(b.id)).count() == 0


class TestComputeFee:
    def _flat(self, val):
        return FeePreset(
            name="ATM", currency="EGP", calc_type="flat", value=Decimal(str(val))
        )

    def _percent(self, val, lo=None, hi=None):
        return FeePreset(
            name="InstaPay",
            currency="EGP",
            calc_type="percent",
            value=Decimal(str(val)),
            min_fee=Decimal(str(lo)) if lo is not None else None,
            max_fee=Decimal(str(hi)) if hi is not None else None,
        )

    def test_flat_returns_value(self):
        assert compute_fee(self._flat("5.00"), 1000) == Decimal("5.00")
        assert compute_fee(self._flat("5.00"), 100000) == Decimal("5.00")

    def test_percent_unclamped(self):
        assert compute_fee(self._percent("0.01"), 1000) == Decimal("10.00")

    def test_percent_clamped_min(self):
        # 100 * 0.001 = 0.10, clamped up to 0.50
        assert compute_fee(self._percent("0.001", "0.50", "20"), 100) == Decimal("0.50")

    def test_percent_clamped_max(self):
        # 100000 * 0.001 = 100, clamped down to 20
        assert compute_fee(self._percent("0.001", "0.50", "20"), 100000) == Decimal(
            "20.00"
        )

    def test_percent_in_range(self):
        # 5000 * 0.001 = 5.00, between 0.5 and 20
        assert compute_fee(self._percent("0.001", "0.50", "20"), 5000) == Decimal(
            "5.00"
        )

    def test_negative_amount_uses_abs(self):
        assert compute_fee(self._percent("0.001"), -5000) == Decimal("5.00")

    def test_compute_method(self):
        p = self._flat("3.50")
        assert p.compute(999) == Decimal("3.50")
