"""Tests for settings app views."""

import datetime
import uuid
from decimal import Decimal

import pytest
from django.test import Client

from tests.factories import (
    AccountFactory,
    CategoryFactory,
    CurrencyFactory,
    InstitutionFactory,
    TransactionFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestSettingsPage:
    def test_renders_200(self, auth_client: Client) -> None:
        CurrencyFactory(code="EGP", name="Egyptian Pound", display_order=0)
        response = auth_client.get("/settings")
        assert response.status_code == 200

    def test_unauthenticated_redirects(self) -> None:
        client = Client()
        response = client.get("/settings")
        assert response.status_code == 302

    def test_settings_shows_currency_controls(self, auth_client: Client) -> None:
        CurrencyFactory(code="EGP", name="Egyptian Pound", display_order=0)
        CurrencyFactory(code="EUR", name="Euro", display_order=1)
        response = auth_client.get("/settings")
        assert response.status_code == 200
        assert b"Display Currency" in response.content
        assert b"EUR" in response.content


@pytest.mark.django_db
class TestCurrencySettings:
    def test_can_update_active_currencies(
        self, auth_client: Client, auth_user: tuple[str, str, str]
    ) -> None:
        CurrencyFactory(code="EGP", name="Egyptian Pound", display_order=0)
        CurrencyFactory(code="EUR", name="Euro", display_order=1)

        response = auth_client.post(
            "/settings/currencies",
            {"active_currency_codes": ["EGP", "EUR"]},
        )
        assert response.status_code == 302

        page = auth_client.get("/settings")
        assert b"EUR" in page.content

    def test_can_update_display_currency(
        self, auth_client: Client, auth_user: tuple[str, str, str]
    ) -> None:
        CurrencyFactory(code="EGP", name="Egyptian Pound", display_order=0)
        CurrencyFactory(code="EUR", name="Euro", display_order=1)
        auth_client.post(
            "/settings/currencies",
            {"active_currency_codes": ["EGP", "EUR"]},
        )

        response = auth_client.post(
            "/settings/display-currency",
            {"currency": "EUR", "next": "/settings"},
        )
        assert response.status_code == 302

        page = auth_client.get("/settings")
        assert b'value="EUR" selected' in page.content


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

    def test_cannot_export_other_users_transactions(
        self, auth_user: tuple[str, str, str], auth_client: Client
    ) -> None:
        """User A's CSV export must not include user B's transactions."""
        user_a_id, _, _ = auth_user

        # User A's transaction
        inst_a = InstitutionFactory(user_id=user_a_id)
        acct_a = AccountFactory(user_id=user_a_id, institution_id=inst_a.id)
        TransactionFactory(
            user_id=user_a_id,
            account_id=acct_a.id,
            type="expense",
            amount=Decimal("100"),
            currency="EGP",
            date=datetime.date(2026, 3, 15),
            note="user_a_tx",
        )

        # User B's transaction (same date range)
        user_b = UserFactory()
        inst_b = InstitutionFactory(user_id=str(user_b.id))
        acct_b = AccountFactory(user_id=str(user_b.id), institution_id=inst_b.id)
        TransactionFactory(
            user_id=str(user_b.id),
            account_id=acct_b.id,
            type="expense",
            amount=Decimal("999"),
            currency="EGP",
            date=datetime.date(2026, 3, 15),
            note="user_b_secret",
        )

        response = auth_client.get("/export/transactions?from=2026-03-01&to=2026-03-31")
        assert response.status_code == 200
        content = response.content.decode()
        assert "user_a_tx" in content
        assert "user_b_secret" not in content
        lines = content.strip().split("\n")
        assert len(lines) == 2  # header + 1 row (user A's only)

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
        CategoryFactory(user_id=user_id, name={"en": "Food"}, is_system=True)
        response = auth_client.get("/settings/categories")
        assert response.status_code == 200
        assert b"Food" in response.content

    def test_shows_usage_count(
        self, auth_user: tuple[str, str, str], auth_client: Client
    ) -> None:
        user_id, _, _ = auth_user
        cat = CategoryFactory(user_id=user_id, name={"en": "Groceries"})
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
        CategoryFactory(user_id=user_id, name={"en": "OldCat"}, is_archived=True)
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
        CategoryFactory(user_id=user_id, name={"en": "Existing"})
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
        cat = CategoryFactory(
            user_id=user_id, name={"en": "ToArchive"}, is_system=False
        )
        response = auth_client.post(f"/settings/categories/{cat.id}/archive")
        assert response.status_code == 302

    def test_archive_system_returns_403(
        self, auth_user: tuple[str, str, str], auth_client: Client
    ) -> None:
        user_id, _, _ = auth_user
        cat = CategoryFactory(user_id=user_id, name={"en": "System"}, is_system=True)
        response = auth_client.post(f"/settings/categories/{cat.id}/archive")
        assert response.status_code == 403


@pytest.mark.django_db
class TestCategoryUnarchive:
    def test_unarchive(
        self, auth_user: tuple[str, str, str], auth_client: Client
    ) -> None:
        user_id, _, _ = auth_user
        cat = CategoryFactory(
            user_id=user_id, name={"en": "Archived"}, is_archived=True
        )
        response = auth_client.post(f"/settings/categories/{cat.id}/unarchive")
        assert response.status_code == 302


@pytest.mark.django_db
class TestCategoryUpdate:
    def test_update_custom(
        self, auth_user: tuple[str, str, str], auth_client: Client
    ) -> None:
        user_id, _, _ = auth_user
        cat = CategoryFactory(user_id=user_id, name={"en": "OldName"}, is_system=False)
        response = auth_client.post(
            f"/settings/categories/{cat.id}/update",
            {"name": "NewName", "icon": "✏️"},
        )
        assert response.status_code == 302

    def test_update_system_returns_403(
        self, auth_user: tuple[str, str, str], auth_client: Client
    ) -> None:
        user_id, _, _ = auth_user
        cat = CategoryFactory(user_id=user_id, name={"en": "SysCat"}, is_system=True)
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


@pytest.mark.django_db
class TestLogoutConfirmation:
    """Logout requires confirmation to prevent accidental logouts."""

    def test_logout_has_confirmation_dialog(self, auth_client: Client) -> None:
        """Settings page includes a logout confirmation dialog."""
        response = auth_client.get("/settings")
        content = response.content.decode()
        assert 'id="logout-confirm-dialog"' in content

    def test_logout_button_opens_dialog(self, auth_client: Client) -> None:
        """Logout button triggers confirmation dialog, not direct POST."""
        response = auth_client.get("/settings")
        content = response.content.decode()
        # The visible logout button should open a dialog, not submit the form directly
        assert "logout-confirm-dialog" in content
        assert 'role="dialog"' in content
