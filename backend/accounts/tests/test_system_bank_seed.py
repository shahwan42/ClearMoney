"""Tests for Egypt SystemBank seed migration (#508).

Migration runs at test DB setup, so all rows already exist when tests run.
We verify count, ordering, SVG file presence, and idempotency.
"""

from pathlib import Path

import pytest
from django.conf import settings

from importlib import import_module

from accounts.models import SystemBank

_seed_module = import_module("accounts.migrations.0011_seed_egypt_system_banks")
EGYPT_BANKS = _seed_module.EGYPT_BANKS
seed_banks = _seed_module.seed_banks


@pytest.mark.django_db
class TestEgyptSeed:
    def test_all_20_banks_seeded(self):
        assert SystemBank.objects.filter(country="EG").count() == 20

    def test_display_order_matches_priority(self):
        codes = list(
            SystemBank.objects.filter(country="EG")
            .order_by("display_order")
            .values_list("short_name", flat=True)
        )
        expected = [row[0] for row in EGYPT_BANKS]
        assert codes == expected

    def test_all_banks_have_bilingual_names(self):
        for bank in SystemBank.objects.filter(country="EG"):
            assert "en" in bank.name and bank.name["en"]
            assert "ar" in bank.name and bank.name["ar"]

    def test_svg_files_exist_in_static_dir(self):
        static_dir = Path(settings.STATICFILES_DIRS[0])
        for bank in SystemBank.objects.filter(country="EG"):
            svg = static_dir / bank.svg_path
            assert svg.exists(), f"missing static asset: {bank.svg_path}"

    def test_bank_types_correct(self):
        assert SystemBank.objects.get(short_name="InstaPay").bank_type == "fintech"
        assert SystemBank.objects.get(short_name="Vodafone Cash").bank_type == "wallet"
        assert SystemBank.objects.get(short_name="CIB").bank_type == "bank"

    def test_seed_idempotent(self):
        before = SystemBank.objects.filter(country="EG").count()
        # apps fake stub — seed_banks only needs apps.get_model
        from django.apps import apps as real_apps

        class _StubApps:
            def get_model(self, *args, **kwargs):
                return real_apps.get_model(*args, **kwargs)

        seed_banks(_StubApps(), None)
        after = SystemBank.objects.filter(country="EG").count()
        assert before == after == 20

    def test_arabic_names_are_arabic(self):
        cib = SystemBank.objects.get(short_name="CIB")
        assert "البنك" in cib.name["ar"]
        nbe = SystemBank.objects.get(short_name="NBE")
        assert "الأهلي" in nbe.name["ar"]
