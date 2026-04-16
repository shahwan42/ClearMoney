from decimal import Decimal

import pytest

from tests.factories import AccountFactory, InstitutionFactory, UserFactory
from transactions.models import Transaction
from transactions.services import CsvImportService


@pytest.fixture
def test_user_id(db):
    user = UserFactory()
    return str(user.id)

@pytest.fixture
def csv_service(test_user_id):
    return CsvImportService(test_user_id, "UTC")

@pytest.fixture
def target_account(test_user_id):
    inst = InstitutionFactory(user_id=test_user_id)
    return AccountFactory(
        user_id=test_user_id,
        institution_id=inst.id,
        name="Test Account",
        currency="USD",
        current_balance=Decimal("0.00"),
        type="depository",
    )

@pytest.mark.django_db
def test_csv_parse_headers(csv_service):
    csv_content = "Date,Amount,Type,Note\n2023-01-01,100.00,CR,Test"
    headers = csv_service.parse_headers(csv_content)
    assert headers == ["Date", "Amount", "Type", "Note"]

@pytest.mark.django_db
def test_csv_parse_rows_validation_and_classification(csv_service, target_account):
    csv_content = """Date,Amount,Type,Note
2023-01-01,100.00,Deposit,Test Note
01/02/2023,-50.50,,negative amount implies expense
invalid_date,10.00,CR,bad date
2023-01-04,invalid,CR,bad amount"""

    mapping = {
        "date": "Date",
        "amount": "Amount",
        "type": "Type",
        "note": "Note"
    }

    parsed, duplicates, errors = csv_service.parse_rows(csv_content, mapping, str(target_account.id))

    assert len(parsed) == 2
    assert len(errors) == 2

    assert "Invalid date format: invalid_date" in errors[0]
    assert "Invalid amount format: invalid" in errors[1]

    # Row 1
    assert parsed[0]["date"] == "2023-01-01"
    assert parsed[0]["amount"] == "100.00"
    assert parsed[0]["type"] == "income"
    assert parsed[0]["note"] == "Test Note"
    assert parsed[0]["account_id"] == str(target_account.id)

    # Row 2 (negative amount -> expense, amount becomes absolute)
    assert parsed[1]["date"] == "2023-01-02"
    assert parsed[1]["amount"] == "50.50"
    assert parsed[1]["type"] == "expense"
    assert parsed[1]["note"] == "negative amount implies expense"

@pytest.mark.django_db
def test_csv_parse_duplicate_detection(csv_service, target_account, test_user_id):
    csv_content = """Date,Amount,Type,Note
2023-01-01,100.00,Credit,Test Note Duplicate
2023-01-02,50.00,Debit,New Note"""

    mapping = {
        "date": "Date",
        "amount": "Amount",
        "type": "Type",
        "note": "Note"
    }

    # pre-create a transaction that matches row 1 completely
    Transaction.objects.create(
        user_id=test_user_id,
        account_id=str(target_account.id),
        date="2023-01-01",
        amount=Decimal("100.00"),
        type="income",
        note="Test Note Duplicate",
        balance_delta=Decimal("100.00"),
        currency="USD"
    )

    parsed, duplicates, errors = csv_service.parse_rows(csv_content, mapping, str(target_account.id))

    assert len(parsed) == 2
    assert len(duplicates) == 1
    assert len(errors) == 0

    assert parsed[0]["is_duplicate"] is True
    assert parsed[1]["is_duplicate"] is False
