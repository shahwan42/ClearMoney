"""Tests for currency deactivation guardrails."""

import pytest
from auth_app.currency import set_user_active_currencies
from tests.factories import AccountFactory, UserFactory, CurrencyFactory, InstitutionFactory


@pytest.mark.django_db
class TestCurrencyGuardrails:
    def setup_method(self) -> None:
        self.user = UserFactory()
        self.uid = str(self.user.id)
        self.inst = InstitutionFactory(user_id=self.uid)
        CurrencyFactory(code="EGP", is_enabled=True)
        CurrencyFactory(code="USD", is_enabled=True)
        CurrencyFactory(code="EUR", is_enabled=True)

    def test_deactivate_unused_currency_success(self) -> None:
        """User can deactivate a currency they are not using."""
        # Initial active: EGP
        set_user_active_currencies(self.uid, ["EGP", "USD"])
        
        # Deactivate USD (not used)
        set_user_active_currencies(self.uid, ["EGP"])
        
        from auth_app.currency import get_user_active_currency_codes
        assert get_user_active_currency_codes(self.uid) == ["EGP"]

    def test_deactivate_in_use_currency_fails(self) -> None:
        """User cannot deactivate a currency referenced by an account."""
        set_user_active_currencies(self.uid, ["EGP", "USD"])
        
        # Create an account in USD
        AccountFactory(user_id=self.uid, institution_id=self.inst.id, currency="USD")
        
        # Try to deactivate USD
        with pytest.raises(ValueError, match="Cannot deactivate USD because it is referenced by existing data"):
            set_user_active_currencies(self.uid, ["EGP"])

    def test_deactivate_multiple_in_use_fails(self) -> None:
        """Error message mentions the first in-use currency found."""
        set_user_active_currencies(self.uid, ["EGP", "USD", "EUR"])
        
        AccountFactory(user_id=self.uid, institution_id=self.inst.id, currency="EUR")
        
        with pytest.raises(ValueError, match="Cannot deactivate EUR"):
            set_user_active_currencies(self.uid, ["EGP"])
