"""Tests for fee preset services."""

from decimal import Decimal

import pytest
from django.core.exceptions import ObjectDoesNotExist

from fee_presets.models import FeePreset
from fee_presets.services import (
    DEFAULT_EGP_PRESETS,
    FeePresetService,
    seed_default_fee_presets,
)
from tests.factories import UserFactory


@pytest.mark.django_db
class TestSeedDefaults:
    def test_seeds_egp_defaults(self):
        user = UserFactory()
        n = seed_default_fee_presets(str(user.id))
        assert n == len(DEFAULT_EGP_PRESETS)
        names = set(
            FeePreset.objects.for_user(str(user.id)).values_list("name", flat=True)
        )
        assert {"InstaPay", "ATM"} <= names

    def test_idempotent(self):
        user = UserFactory()
        seed_default_fee_presets(str(user.id))
        n2 = seed_default_fee_presets(str(user.id))
        assert n2 == 0
        assert FeePreset.objects.for_user(str(user.id)).count() == len(
            DEFAULT_EGP_PRESETS
        )

    def test_per_user(self):
        a = UserFactory()
        b = UserFactory()
        seed_default_fee_presets(str(a.id))
        assert FeePreset.objects.for_user(str(a.id)).count() == 2
        assert FeePreset.objects.for_user(str(b.id)).count() == 0


@pytest.mark.django_db
class TestService:
    def test_create_flat(self):
        user = UserFactory()
        svc = FeePresetService(str(user.id))
        p = svc.create(
            name="Wire",
            currency="USD",
            calc_type="flat",
            value="10",
        )
        assert p.id is not None

    def test_create_percent_with_clamps(self):
        user = UserFactory()
        svc = FeePresetService(str(user.id))
        p = svc.create(
            name="InstaPay",
            currency="EGP",
            calc_type="percent",
            value="0.001",
            min_fee="0.5",
            max_fee="20",
        )
        assert p.min_fee == Decimal("0.5")

    def test_create_rejects_zero_value(self):
        user = UserFactory()
        svc = FeePresetService(str(user.id))
        with pytest.raises(ValueError):
            svc.create(name="X", currency="EGP", calc_type="flat", value="0")

    def test_create_rejects_percent_above_one(self):
        user = UserFactory()
        svc = FeePresetService(str(user.id))
        with pytest.raises(ValueError):
            svc.create(name="X", currency="EGP", calc_type="percent", value="1.5")

    def test_create_rejects_min_gt_max(self):
        user = UserFactory()
        svc = FeePresetService(str(user.id))
        with pytest.raises(ValueError):
            svc.create(
                name="X",
                currency="EGP",
                calc_type="percent",
                value="0.01",
                min_fee="100",
                max_fee="10",
            )

    def test_create_rejects_invalid_calc_type(self):
        user = UserFactory()
        svc = FeePresetService(str(user.id))
        with pytest.raises(ValueError):
            svc.create(name="X", currency="EGP", calc_type="bogus", value="1")

    def test_list_active_filters_archived(self):
        user = UserFactory()
        svc = FeePresetService(str(user.id))
        p1 = svc.create(name="A", currency="EGP", calc_type="flat", value="1")
        svc.create(name="B", currency="EGP", calc_type="flat", value="2")
        svc.archive(str(p1.id))
        active = svc.list_active()
        assert {p["name"] for p in active} == {"B"}

    def test_list_active_currency_filter(self):
        user = UserFactory()
        svc = FeePresetService(str(user.id))
        svc.create(name="ATM", currency="EGP", calc_type="flat", value="5")
        svc.create(name="ATM-USD", currency="USD", calc_type="flat", value="2")
        egp = svc.list_active("EGP")
        assert {p["name"] for p in egp} == {"ATM"}

    def test_archive_then_unarchive(self):
        user = UserFactory()
        svc = FeePresetService(str(user.id))
        p = svc.create(name="A", currency="EGP", calc_type="flat", value="1")
        svc.archive(str(p.id))
        assert svc.get(str(p.id)).archived is True
        svc.unarchive(str(p.id))
        assert svc.get(str(p.id)).archived is False

    def test_get_other_users_preset_raises(self):
        a = UserFactory()
        b = UserFactory()
        svc_a = FeePresetService(str(a.id))
        p = svc_a.create(name="A", currency="EGP", calc_type="flat", value="1")
        svc_b = FeePresetService(str(b.id))
        with pytest.raises(ObjectDoesNotExist):
            svc_b.get(str(p.id))

    def test_compute_via_service(self):
        user = UserFactory()
        svc = FeePresetService(str(user.id))
        p = svc.create(
            name="InstaPay",
            currency="EGP",
            calc_type="percent",
            value="0.001",
            min_fee="0.5",
            max_fee="20",
        )
        assert svc.compute(str(p.id), 5000) == Decimal("5.00")
        assert svc.compute(str(p.id), 100) == Decimal("0.50")
        assert svc.compute(str(p.id), 100000) == Decimal("20.00")

    def test_update_validates(self):
        user = UserFactory()
        svc = FeePresetService(str(user.id))
        p = svc.create(name="A", currency="EGP", calc_type="flat", value="5")
        with pytest.raises(ValueError):
            svc.update(str(p.id), value=Decimal("0"))
