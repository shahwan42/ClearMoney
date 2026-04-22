"""Tests for dynamic currency registry and user preferences."""

import pytest

from auth_app.currency import (
    get_user_active_currency_codes,
    get_user_selected_display_currency,
    set_user_active_currencies,
    set_user_selected_display_currency,
)
from tests.factories import CurrencyFactory, UserCurrencyPreferenceFactory, UserFactory


@pytest.mark.django_db
class TestCurrencyPreferences:
    def test_creates_default_preferences_when_missing(self) -> None:
        CurrencyFactory(code="EGP", name="Egyptian Pound", display_order=0)
        user = UserFactory()

        assert get_user_active_currency_codes(str(user.id)) == ["EGP"]
        assert get_user_selected_display_currency(str(user.id)) == "EGP"

    def test_filters_out_disabled_or_unknown_codes(self) -> None:
        CurrencyFactory(code="EGP", name="Egyptian Pound", display_order=0)
        CurrencyFactory(code="EUR", name="Euro", display_order=1)
        user = UserFactory()
        UserCurrencyPreferenceFactory(
            user=user,
            active_currency_codes=["EUR", "BOGUS", "EUR"],
            selected_display_currency="USD",
        )

        assert get_user_active_currency_codes(str(user.id)) == ["EUR"]
        assert get_user_selected_display_currency(str(user.id)) == "EUR"

    def test_set_active_currencies_requires_at_least_one(self) -> None:
        CurrencyFactory(code="EGP", name="Egyptian Pound", display_order=0)
        user = UserFactory()

        with pytest.raises(ValueError, match="at least one"):
            set_user_active_currencies(str(user.id), [])

    def test_selected_currency_must_be_active(self) -> None:
        CurrencyFactory(code="EGP", name="Egyptian Pound", display_order=0)
        CurrencyFactory(code="EUR", name="Euro", display_order=1)
        user = UserFactory()
        set_user_active_currencies(str(user.id), ["EGP"])

        with pytest.raises(ValueError, match="must be active"):
            set_user_selected_display_currency(str(user.id), "EUR")

    def test_setting_active_currencies_rehomes_selected_currency(self) -> None:
        CurrencyFactory(code="EGP", name="Egyptian Pound", display_order=0)
        CurrencyFactory(code="EUR", name="Euro", display_order=1)
        user = UserFactory()
        set_user_active_currencies(str(user.id), ["EGP", "EUR"])
        set_user_selected_display_currency(str(user.id), "EUR")

        set_user_active_currencies(str(user.id), ["EGP"])

        assert get_user_selected_display_currency(str(user.id)) == "EGP"
