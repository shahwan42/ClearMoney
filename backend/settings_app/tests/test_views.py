"""Tests for settings app views."""

import datetime
from decimal import Decimal

import pytest
from django.test import Client

from tests.factories import (
    AccountFactory,
    CategoryFactory,
    InstitutionFactory,
    TransactionFactory,
)


@pytest.mark.django_db
class TestSettingsPage:
    def test_renders_200(self, auth_client: Client) -> None:
        response = auth_client.get("/settings")
        assert response.status_code == 200

    def test_unauthenticated_redirects(self) -> None:
        client = Client()
        response = client.get("/settings")
        assert response.status_code == 302


@pytest.mark.django_db
class TestExportTransactions:
    def test_csv_download(
        self, auth_user: tuple[str, str, str], auth_client: Client
    ) -> None:
        user_id, _, _ = auth_user
        inst = InstitutionFactory(user_id=user_id)
        account = AccountFactory(
            user_id=user_id, institution_id=inst.id, currency="EGP"
        )
        category = CategoryFactory(user_id=user_id, type="expense")
        TransactionFactory(
            user_id=user_id,
            account_id=account.id,
            category_id=category.id,
            type="expense",
            amount=Decimal("100"),
            currency="EGP",
            date=datetime.date(2026, 3, 15),
        )
        response = auth_client.get("/export/transactions?from=2026-03-01&to=2026-03-31")
        assert response.status_code == 200
        assert response["Content-Type"] == "text/csv"
        assert "Content-Disposition" in response
        content = response.content.decode()
        assert "Date" in content
        assert "100" in content

    def test_empty_range(self, auth_client: Client) -> None:
        response = auth_client.get("/export/transactions?from=2020-01-01&to=2020-01-31")
        assert response.status_code == 200
        assert response["Content-Type"] == "text/csv"
        lines = response.content.decode().strip().split("\n")
        assert len(lines) == 1  # Just the header

    def test_invalid_date_format(self, auth_client: Client) -> None:
        response = auth_client.get("/export/transactions?from=abc&to=def")
        assert response.status_code == 400

    def test_missing_params(self, auth_client: Client) -> None:
        response = auth_client.get("/export/transactions")
        assert response.status_code == 400

    def test_csv_filename(self, auth_client: Client) -> None:
        response = auth_client.get("/export/transactions?from=2026-03-01&to=2026-03-31")
        disposition = response["Content-Disposition"]
        assert "transactions" in disposition
        assert ".csv" in disposition

    def test_csv_null_category_outputs_empty_string(
        self, auth_user: tuple[str, str, str], auth_client: Client
    ) -> None:
        """Transaction with no category → CSV cell is empty string, not 'None'."""  # gap: data
        user_id, _, _ = auth_user
        inst = InstitutionFactory(user_id=user_id)
        account = AccountFactory(user_id=user_id, institution_id=inst.id)
        TransactionFactory(
            user_id=user_id,
            account_id=account.id,
            category_id=None,
            type="expense",
            amount=Decimal("50"),
            currency="EGP",
            date=datetime.date(2026, 3, 15),
        )
        response = auth_client.get("/export/transactions?from=2026-03-01&to=2026-03-31")
        assert response.status_code == 200
        content = response.content.decode()
        assert "None" not in content  # category_id must not stringify as "None"

    def test_csv_null_note_outputs_empty_string(
        self, auth_user: tuple[str, str, str], auth_client: Client
    ) -> None:
        """Transaction with no note → CSV cell is empty string, not 'None'."""  # gap: data
        user_id, _, _ = auth_user
        inst = InstitutionFactory(user_id=user_id)
        account = AccountFactory(user_id=user_id, institution_id=inst.id)
        TransactionFactory(
            user_id=user_id,
            account_id=account.id,
            note=None,
            type="expense",
            amount=Decimal("75"),
            currency="EGP",
            date=datetime.date(2026, 3, 15),
        )
        response = auth_client.get("/export/transactions?from=2026-03-01&to=2026-03-31")
        assert response.status_code == 200
        content = response.content.decode()
        assert "None" not in content  # note must not stringify as "None"

    def test_unauthenticated_redirects(self) -> None:
        client = Client()
        response = client.get("/export/transactions?from=2026-03-01&to=2026-03-31")
        assert response.status_code == 302
