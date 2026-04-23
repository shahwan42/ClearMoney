
import pytest
from zoneinfo import ZoneInfo
from decimal import Decimal
from budgets.services import BudgetService
from tests.factories import UserFactory, CategoryFactory, CurrencyFactory, InstitutionFactory, AccountFactory
from auth_app.currency import set_user_active_currencies

TZ = ZoneInfo("Africa/Cairo")

@pytest.fixture
def multi_currency_data(db):
    user = UserFactory()
    user_id = str(user.id)
    
    # Enable multiple currencies
    CurrencyFactory(code="EGP", is_enabled=True)
    CurrencyFactory(code="USD", is_enabled=True)
    CurrencyFactory(code="EUR", is_enabled=True)
    set_user_active_currencies(user_id, ["EGP", "USD", "EUR"])
    
    cat = CategoryFactory(user_id=user.id, name={"en": "Food"}, type="expense")
    
    # Institution and account for transactions
    inst = InstitutionFactory(user_id=user.id)
    acc_egp = AccountFactory(user_id=user.id, institution_id=inst.id, currency="EGP")
    acc_usd = AccountFactory(user_id=user.id, institution_id=inst.id, currency="USD")
    acc_eur = AccountFactory(user_id=user.id, institution_id=inst.id, currency="EUR")
    
    return {
        "user_id": user_id,
        "cat_id": str(cat.id),
        "acc_egp_id": str(acc_egp.id),
        "acc_usd_id": str(acc_usd.id),
        "acc_eur_id": str(acc_eur.id),
    }

@pytest.mark.django_db
class TestBudgetMultiCurrency:
    def test_budget_crud_in_third_currency(self, multi_currency_data):
        svc = BudgetService(multi_currency_data["user_id"], TZ)
        
        # Create budget in EUR
        budget = svc.create(multi_currency_data["cat_id"], 100.0, "EUR")
        assert budget["currency"] == "EUR"
        assert budget["monthly_limit"] == 100.0
        
        # Read
        budgets = svc.get_all_with_spending()
        eur_budgets = [b for b in budgets if b.currency == "EUR"]
        assert len(eur_budgets) == 1
        assert eur_budgets[0].monthly_limit == 100.0
        
        # Update
        svc.update(budget["id"], monthly_limit=150.0)
        updated = svc.get_all_with_spending()
        # Filtering is important here as get_all_with_spending returns all
        eur_updated = [b for b in updated if b.id == budget["id"]][0]
        assert eur_updated.monthly_limit == 150.0
        
        # Delete
        svc.delete(budget["id"])
        final = svc.get_all_with_spending()
        assert not any(b.id == budget["id"] for b in final)

    def test_total_budget_crud_in_third_currency(self, multi_currency_data):
        svc = BudgetService(multi_currency_data["user_id"], TZ)
        
        # Set total budget in USD
        total = svc.set_total_budget(Decimal("500.00"), "USD")
        assert total["currency"] == "USD"
        assert total["monthly_limit"] == Decimal("500.00")
        
        # Get all
        totals = svc.get_active_total_budgets()
        assert any(t["currency"] == "USD" and t["monthly_limit"] == Decimal("500.00") for t in totals)
        
        # Delete
        svc.delete_total_budget("USD")
        totals_after = svc.get_active_total_budgets()
        assert not any(t["currency"] == "USD" for t in totals_after)

    def test_inactive_currency_rejection(self, multi_currency_data):
        svc = BudgetService(multi_currency_data["user_id"], TZ)
        
        # JPY is not active for this user
        with pytest.raises(ValueError, match="Invalid currency: JPY"):
            svc.create(multi_currency_data["cat_id"], 1000.0, "JPY")
            
        with pytest.raises(ValueError, match="Invalid currency: JPY"):
            svc.set_total_budget(Decimal("1000.00"), "JPY")

    def test_multiple_total_budgets_loading(self, multi_currency_data):
        svc = BudgetService(multi_currency_data["user_id"], TZ)
        
        svc.set_total_budget(Decimal("10000"), "EGP")
        svc.set_total_budget(Decimal("500"), "USD")
        
        totals = svc.get_active_total_budgets()
        assert len(totals) == 2
        currencies = {t["currency"] for t in totals}
        assert currencies == {"EGP", "USD"}
