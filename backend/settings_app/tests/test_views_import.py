import json
import pytest
from django.urls import reverse
from django.core.cache import cache
from transactions.models import Transaction
from accounts.models import Account
from tests.factories import AccountFactory, InstitutionFactory
from decimal import Decimal
from django.core.files.uploadedfile import SimpleUploadedFile

@pytest.mark.django_db
def test_csv_import_wizard_flow(auth_client, auth_user):
    user_id, email, token = auth_user

    # Step 0: Setup target account
    inst = InstitutionFactory(user_id=user_id)
    account = AccountFactory(
        user_id=user_id,
        institution_id=inst.id,
        name="Target Account",
        currency="USD",
        current_balance=Decimal("100.00"),
        type="depository",
    )

    # Step 1: Upload CSV
    url_upload = reverse("import-upload")
    
    csv_content = b"Date,Amount,Type,Note\n2023-05-01,100.00,CR,Import Test"
    file = SimpleUploadedFile("statement.csv", csv_content, content_type="text/csv")
    
    response = auth_client.post(url_upload, {"file": file})
    assert response.status_code == 302
    
    # redirect url is settings/import/<import_id>/mapping
    redirect_url = response.url
    import_id = redirect_url.split("/")[-2]

    # Step 2: Mapping
    response = auth_client.get(redirect_url)
    assert response.status_code == 200
    assert "Amount" in response.content.decode()

    # Post mapping
    response = auth_client.post(redirect_url, {
        "account_id": str(account.id),
        "col_date": "Date",
        "col_amount": "Amount",
        "col_type": "Type",
        "col_note": "Note",
    })
    
    assert response.status_code == 302
    redirect_url_preview = response.url
    assert "preview" in redirect_url_preview

    # Step 3: Preview and Process
    response = auth_client.get(redirect_url_preview)
    assert response.status_code == 200
    assert "Import Test" in response.content.decode()

    # Post confirm
    response = auth_client.post(redirect_url_preview)
    assert response.status_code == 302
    redirect_url_summary = response.url
    assert "summary" in redirect_url_summary

    # Step 4: Summary
    response = auth_client.get(redirect_url_summary)
    assert response.status_code == 200

    # Ensure transaction was created
    tx = Transaction.objects.filter(note="Import Test").first()
    assert tx is not None
    assert tx.amount == Decimal("100.00")
    assert tx.type == "income"
    assert tx.account_id == account.id

    # Check atomic update of account balance
    account.refresh_from_db()
    assert account.current_balance == Decimal("200.00")  # 100 + 100
