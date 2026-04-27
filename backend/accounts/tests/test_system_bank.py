"""Tests for SystemBank model — bilingual name resolution + admin registration."""

import pytest
from django.contrib import admin

from accounts.models import SystemBank


@pytest.mark.django_db
class TestSystemBankModel:
    def test_create_with_bilingual_name(self):
        bank = SystemBank.objects.create(
            name={"en": "CIB", "ar": "البنك التجاري الدولي"},
            short_name="CIB",
            svg_path="banks/cib.svg",
            brand_color="#003366",
        )
        assert bank.pk is not None
        assert bank.country == "EG"
        assert bank.bank_type == "bank"
        assert bank.is_active is True

    def test_get_display_name_en(self):
        bank = SystemBank(
            name={"en": "CIB", "ar": "البنك التجاري الدولي"},
            short_name="CIB",
        )
        assert bank.get_display_name("en") == "CIB"

    def test_get_display_name_ar(self):
        bank = SystemBank(
            name={"en": "CIB", "ar": "البنك التجاري الدولي"},
            short_name="CIB",
        )
        assert bank.get_display_name("ar") == "البنك التجاري الدولي"

    def test_get_display_name_locale_with_region(self):
        bank = SystemBank(name={"en": "CIB", "ar": "سيب"}, short_name="CIB")
        assert bank.get_display_name("ar-EG") == "سيب"

    def test_get_display_name_missing_lang_falls_back_to_en(self):
        bank = SystemBank(name={"en": "QNB"}, short_name="QNB")
        assert bank.get_display_name("ar") == "QNB"

    def test_get_display_name_empty_falls_back_to_short_name(self):
        bank = SystemBank(name={}, short_name="HSBC")
        assert bank.get_display_name("en") == "HSBC"

    def test_get_display_name_default_uses_active_language(self, db):
        bank = SystemBank.objects.create(
            name={"en": "NBE", "ar": "الأهلي"}, short_name="NBE"
        )
        # default get_language() in tests is "en-us"
        assert bank.get_display_name() in ("NBE", "الأهلي")

    def test_str_includes_short_name_and_country(self):
        bank = SystemBank(name={"en": "CIB"}, short_name="CIB", country="EG")
        assert str(bank) == "CIB (EG)"

    def test_admin_registered(self):
        assert admin.site.is_registered(SystemBank)
