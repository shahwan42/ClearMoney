"""Tests for settings app views."""

import datetime
import uuid
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


@pytest.mark.django_db
class TestCsvEdgeCases:
    """Edge cases for CSV export."""  # gap: data

    def test_csv_from_after_to_returns_empty(self, auth_client: Client) -> None:
        """Date range where from > to returns CSV with header only."""  # gap: data
        response = auth_client.get("/export/transactions?from=2026-03-31&to=2026-03-01")
        assert response.status_code == 200
        assert response["Content-Type"] == "text/csv"
        lines = response.content.decode().strip().split("\n")
        assert len(lines) == 1  # header only, no data rows

    def test_csv_note_with_formula_chars(
        self, auth_user: tuple[str, str, str], auth_client: Client
    ) -> None:
        """Note starting with '=' is exported as-is (documents current behavior)."""  # gap: data
        user_id, _, _ = auth_user
        inst = InstitutionFactory(user_id=user_id)
        account = AccountFactory(
            user_id=user_id, institution_id=inst.id, currency="EGP"
        )
        TransactionFactory(
            user_id=user_id,
            account_id=account.id,
            type="expense",
            amount=Decimal("50"),
            currency="EGP",
            date=datetime.date(2026, 3, 15),
            note="=SUM(A1:A10)",
        )
        response = auth_client.get("/export/transactions?from=2026-03-01&to=2026-03-31")
        assert response.status_code == 200
        content = response.content.decode()
        assert "=SUM(A1:A10)" in content


@pytest.mark.django_db
class TestCategoriesPage:
    def test_renders_200(
        self, auth_user: tuple[str, str, str], auth_client: Client
    ) -> None:
        user_id, _, _ = auth_user
        CategoryFactory(user_id=user_id, name="Food", is_system=True)
        response = auth_client.get("/settings/categories")
        assert response.status_code == 200
        assert b"Food" in response.content

    def test_shows_usage_count(
        self, auth_user: tuple[str, str, str], auth_client: Client
    ) -> None:
        user_id, _, _ = auth_user
        cat = CategoryFactory(user_id=user_id, name="Groceries")
        inst = InstitutionFactory(user_id=user_id)
        acct = AccountFactory(user_id=user_id, institution_id=inst.id)
        TransactionFactory(
            user_id=user_id,
            account_id=acct.id,
            category_id=cat.id,
            amount=Decimal("50"),
        )
        response = auth_client.get("/settings/categories")
        assert response.status_code == 200
        assert b"1 txn" in response.content

    def test_shows_archived_section(
        self, auth_user: tuple[str, str, str], auth_client: Client
    ) -> None:
        user_id, _, _ = auth_user
        CategoryFactory(user_id=user_id, name="OldCat", is_archived=True)
        response = auth_client.get("/settings/categories")
        assert response.status_code == 200
        assert b"Archived" in response.content
        assert b"OldCat" in response.content

    def test_unauthenticated_redirects(self) -> None:
        client = Client()
        response = client.get("/settings/categories")
        assert response.status_code == 302


@pytest.mark.django_db
class TestCategoryAdd:
    def test_add_category(
        self, auth_user: tuple[str, str, str], auth_client: Client
    ) -> None:
        response = auth_client.post(
            "/settings/categories/add",
            {"name": "NewCat", "icon": "🎯"},
        )
        assert response.status_code == 302  # redirect to categories page

    def test_add_empty_name_returns_400(
        self, auth_user: tuple[str, str, str], auth_client: Client
    ) -> None:
        response = auth_client.post(
            "/settings/categories/add",
            {"name": "", "icon": ""},
        )
        assert response.status_code == 400

    def test_add_duplicate_name_returns_400(
        self, auth_user: tuple[str, str, str], auth_client: Client
    ) -> None:
        user_id, _, _ = auth_user
        CategoryFactory(user_id=user_id, name="Existing")
        response = auth_client.post(
            "/settings/categories/add",
            {"name": "existing", "icon": ""},
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestCategoryArchive:
    def test_archive_custom(
        self, auth_user: tuple[str, str, str], auth_client: Client
    ) -> None:
        user_id, _, _ = auth_user
        cat = CategoryFactory(user_id=user_id, name="ToArchive", is_system=False)
        response = auth_client.post(f"/settings/categories/{cat.id}/archive")
        assert response.status_code == 302

    def test_archive_system_returns_403(
        self, auth_user: tuple[str, str, str], auth_client: Client
    ) -> None:
        user_id, _, _ = auth_user
        cat = CategoryFactory(user_id=user_id, name="System", is_system=True)
        response = auth_client.post(f"/settings/categories/{cat.id}/archive")
        assert response.status_code == 403


@pytest.mark.django_db
class TestCategoryUnarchive:
    def test_unarchive(
        self, auth_user: tuple[str, str, str], auth_client: Client
    ) -> None:
        user_id, _, _ = auth_user
        cat = CategoryFactory(user_id=user_id, name="Archived", is_archived=True)
        response = auth_client.post(f"/settings/categories/{cat.id}/unarchive")
        assert response.status_code == 302


@pytest.mark.django_db
class TestCategoryUpdate:
    def test_update_custom(
        self, auth_user: tuple[str, str, str], auth_client: Client
    ) -> None:
        user_id, _, _ = auth_user
        cat = CategoryFactory(user_id=user_id, name="OldName", is_system=False)
        response = auth_client.post(
            f"/settings/categories/{cat.id}/update",
            {"name": "NewName", "icon": "✏️"},
        )
        assert response.status_code == 302

    def test_update_system_returns_403(
        self, auth_user: tuple[str, str, str], auth_client: Client
    ) -> None:
        user_id, _, _ = auth_user
        cat = CategoryFactory(user_id=user_id, name="SysCat", is_system=True)
        response = auth_client.post(
            f"/settings/categories/{cat.id}/update",
            {"name": "Hacked", "icon": ""},
        )
        assert response.status_code == 403

    def test_update_not_found_returns_404(
        self, auth_user: tuple[str, str, str], auth_client: Client
    ) -> None:
        response = auth_client.post(
            f"/settings/categories/{uuid.uuid4()}/update",
            {"name": "Ghost", "icon": ""},
        )
        assert response.status_code == 404
