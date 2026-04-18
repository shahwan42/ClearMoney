"""Tests for fee analytics reports."""

import datetime
from decimal import Decimal
import pytest
from reports.services import get_fee_analytics
from tests.factories import (
    AccountFactory,
    CategoryFactory,
    InstitutionFactory,
    TransactionFactory,
    UserFactory,
)

@pytest.mark.django_db
class TestGetFeeAnalytics:
    """get_fee_analytics() — fee spending analysis."""

    def test_fee_summary(self):
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        account = AccountFactory(
            user_id=user.id, institution_id=inst.id, currency="EGP"
        )
        fees_cat = CategoryFactory(user_id=user.id, name={"en": "Fees & Charges"}, type="expense")

        # Create some fees for March 2026
        TransactionFactory(
            user_id=user.id,
            account_id=account.id,
            category_id=fees_cat.id,
            type="expense",
            amount=Decimal("10.00"),
            currency="EGP",
            date=datetime.date(2026, 3, 10),
            note="Transfer fee"
        )
        TransactionFactory(
            user_id=user.id,
            account_id=account.id,
            category_id=fees_cat.id,
            type="expense",
            amount=Decimal("15.00"),
            currency="EGP",
            date=datetime.date(2026, 3, 20),
            note="InstaPay fee"
        )
        # Fee for Feb 2026
        TransactionFactory(
            user_id=user.id,
            account_id=account.id,
            category_id=fees_cat.id,
            type="expense",
            amount=Decimal("5.00"),
            currency="EGP",
            date=datetime.date(2026, 2, 15),
            note="General fee"
        )

        data = get_fee_analytics(str(user.id), 2026, 3)
        
        assert data["month_total"] == 25.0
        assert data["year_total"] == 30.0
        assert len(data["by_account"]) == 1
        assert data["by_account"][0]["name"] == account.name
        assert data["by_account"][0]["amount"] == 30.0
        
        # Breakdown by type
        # In our case, both are "Transfer" because of note parsing (Transfer and InstaPay)
        # Wait, let's see how they map. 
        # "Transfer fee" -> transfer
        # "InstaPay fee" -> transfer
        assert len(data["by_type"]) == 1
        assert data["by_type"][0]["name"] == "Transfer"
        assert data["by_type"][0]["amount"] == 25.0
        
        # Trend
        assert len(data["trend"]) == 6
        assert data["trend"][-1]["amount"] == 25.0 # March
        assert data["trend"][-2]["amount"] == 5.0  # Feb

    def test_fee_type_by_linked_transaction(self):
        user = UserFactory()
        inst = InstitutionFactory(user_id=user.id)
        account = AccountFactory(user_id=user.id, institution_id=inst.id, currency="EGP")
        fees_cat = CategoryFactory(user_id=user.id, name={"en": "Fees & Charges"}, type="expense")
        
        # Parent transfer
        parent = TransactionFactory(
            user_id=user.id,
            account_id=account.id,
            type="transfer",
            amount=1000,
            date=datetime.date(2026, 3, 1)
        )
        
        # Fee linked to transfer
        TransactionFactory(
            user_id=user.id,
            account_id=account.id,
            category_id=fees_cat.id,
            type="expense",
            amount=Decimal("10.00"),
            date=datetime.date(2026, 3, 1),
            linked_transaction_id=parent.id
        )
        
        data = get_fee_analytics(str(user.id), 2026, 3)
        assert len(data["by_type"]) == 1
        assert data["by_type"][0]["name"] == "Transfer"
        assert data["by_type"][0]["amount"] == 10.0
