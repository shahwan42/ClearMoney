"""Tests for Currency.name JSONB + bilingual display (#512)."""

import pytest
from django.utils.translation import override

from auth_app.currency import get_supported_currencies
from auth_app.models import Currency


@pytest.mark.django_db
class TestCurrencyBilingual:
    def test_egp_has_arabic_name(self):
        cur = Currency.objects.get(code="EGP")
        assert cur.name == {"en": "Egyptian Pound", "ar": "الجنيه المصري"}

    def test_get_display_name_en(self):
        cur = Currency.objects.get(code="EGP")
        assert cur.get_display_name("en") == "Egyptian Pound"

    def test_get_display_name_ar(self):
        cur = Currency.objects.get(code="USD")
        assert cur.get_display_name("ar") == "الدولار الأمريكي"

    def test_get_display_name_locale_with_region(self):
        cur = Currency.objects.get(code="EGP")
        assert cur.get_display_name("ar-EG") == "الجنيه المصري"

    def test_get_display_name_missing_lang_falls_back_to_en(self):
        cur = Currency(code="ZZZ", name={"en": "Test Coin"})
        assert cur.get_display_name("ar") == "Test Coin"

    def test_get_display_name_empty_falls_back_to_code(self):
        cur = Currency(code="ZZZ", name={})
        assert cur.get_display_name("en") == "ZZZ"

    def test_supported_currencies_uses_active_locale(self):
        with override("ar"):
            options = get_supported_currencies()
        names_by_code = {opt.code: opt.name for opt in options}
        assert names_by_code.get("EGP") == "الجنيه المصري"

    def test_supported_currencies_falls_back_to_en(self):
        with override("en"):
            options = get_supported_currencies()
        names_by_code = {opt.code: opt.name for opt in options}
        assert names_by_code.get("EGP") == "Egyptian Pound"

    def test_all_six_seeded_currencies_bilingual(self):
        codes = {"EGP", "USD", "EUR", "GBP", "AED", "SAR"}
        for cur in Currency.objects.filter(code__in=codes):
            assert isinstance(cur.name, dict)
            assert "en" in cur.name
            assert "ar" in cur.name
            assert cur.name["en"]
            assert cur.name["ar"]
