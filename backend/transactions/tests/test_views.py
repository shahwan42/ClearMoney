"""
Transaction view tests — HTTP-level tests for all /transactions/*, /transfers/*,
/exchange/*, /batch-entry, and /fawry-cashout routes.

Uses raw SQL fixtures for test data setup.
"""

import json
import uuid
from datetime import date

import pytest
from django.db import connection

from conftest import SessionFactory, UserFactory, set_auth_cookie
from core.models import Session, User


@pytest.fixture
def tx_view_data(db):
    """User + session + institution + EGP savings account + category."""
    user = UserFactory()
    session = SessionFactory(user=user)
    user_id = str(user.id)
    inst_id = str(uuid.uuid4())
    egp_id = str(uuid.uuid4())
    cat_id = str(uuid.uuid4())

    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO institutions (id, user_id, name, type) VALUES (%s, %s, %s, 'bank')",
            [inst_id, user_id, "Test Bank"],
        )
        cursor.execute(
            "INSERT INTO accounts (id, user_id, institution_id, name, type, currency,"
            " current_balance, initial_balance)"
            " VALUES (%s, %s, %s, %s, 'savings', 'EGP', %s, %s)",
            [egp_id, user_id, inst_id, "EGP Savings", 10000, 10000],
        )
        cursor.execute(
            "INSERT INTO categories (id, user_id, name, type)"
            " VALUES (%s, %s, %s, 'expense')",
            [cat_id, user_id, "Food"],
        )

    yield {
        "user_id": user_id,
        "session_token": session.token,
        "egp_id": egp_id,
        "cat_id": cat_id,
    }

    with connection.cursor() as cursor:
        cursor.execute(
            "DELETE FROM virtual_account_allocations WHERE transaction_id IN (SELECT id FROM transactions WHERE user_id = %s)",
            [user_id],
        )
        cursor.execute("DELETE FROM transactions WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM accounts WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM categories WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM institutions WHERE user_id = %s", [user_id])
    Session.objects.filter(user=user).delete()
    User.objects.filter(id=user.id).delete()


# ---------------------------------------------------------------------------
# Transaction list page
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTransactionsList:
    def test_200(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/transactions")
        assert response.status_code == 200
        assert b"Transactions" in response.content

    def test_partial_returns_fragment(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/transactions/list", HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        # Partial should not contain full page structure
        assert b"<!DOCTYPE" not in response.content

    def test_unauthenticated_redirects(self, client):
        response = client.get("/transactions")
        assert response.status_code == 302
        assert "/login" in response.url


# ---------------------------------------------------------------------------
# Transaction new page
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTransactionNew:
    def test_200(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/transactions/new")
        assert response.status_code == 200
        assert b"New Transaction" in response.content

    def test_prefill_with_dup(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        # Create a transaction first
        tx_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, note, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 500, 'EGP', %s, 'Test note', -500)",
                [
                    tx_id,
                    tx_view_data["user_id"],
                    tx_view_data["egp_id"],
                    date(2026, 3, 15),
                ],
            )
        response = c.get(f"/transactions/new?dup={tx_id}")
        assert response.status_code == 200
        assert b"Test note" in response.content

    def test_form_has_more_options_toggle(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/transactions/new")
        content = response.content.decode()
        assert 'id="more-options"' in content
        assert 'aria-expanded="false"' in content

    def test_hidden_date_defaults_to_today(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/transactions/new")
        content = response.content.decode()
        today = date.today().isoformat()
        assert f'value="{today}"' in content

    def test_note_visible_above_toggle(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/transactions/new")
        content = response.content.decode()
        note_pos = content.index('name="note"')
        toggle_pos = content.index('id="more-options-toggle"')
        assert note_pos < toggle_pos, (
            "note should appear before the More options toggle"
        )

    def test_duplicate_date_shown_in_date_picker(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        tx_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 500, 'EGP', %s, -500)",
                [
                    tx_id,
                    tx_view_data["user_id"],
                    tx_view_data["egp_id"],
                    date(2026, 3, 15),
                ],
            )
        response = c.get(f"/transactions/new?dup={tx_id}")
        assert b'value="2026-03-15"' in response.content

    def test_duplicate_note_prefilled_and_visible(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        tx_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, note, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 500, 'EGP', %s, 'Lunch', -500)",
                [
                    tx_id,
                    tx_view_data["user_id"],
                    tx_view_data["egp_id"],
                    date(2026, 3, 15),
                ],
            )
        response = c.get(f"/transactions/new?dup={tx_id}")
        assert response.status_code == 200
        assert b"Lunch" in response.content
        # Note is now always visible — no auto-expand flag needed
        assert b"data-auto-expand" not in response.content

    def test_date_picker_starts_disabled(self, client, tx_view_data):
        """Date picker must start disabled so only the hidden input submits on collapse."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/transactions/new")
        content = response.content.decode()
        # The visible date picker is disabled; the hidden one is not
        assert 'id="date-picker" disabled' in content
        assert 'id="date-default"' in content
        assert 'id="date-default" disabled' not in content

    def test_hidden_date_input_has_today(self, client, tx_view_data):
        """The hidden date input specifically (not just any element) holds today's date."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/transactions/new")
        content = response.content.decode()
        today = date.today().isoformat()
        assert f'id="date-default" value="{today}"' in content

    def test_duplicate_hidden_date_still_today(self, client, tx_view_data):
        """On dup the hidden input keeps today's date; only the picker shows the original."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        tx_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 500, 'EGP', %s, -500)",
                [
                    tx_id,
                    tx_view_data["user_id"],
                    tx_view_data["egp_id"],
                    date(2026, 3, 15),
                ],
            )
        response = c.get(f"/transactions/new?dup={tx_id}")
        content = response.content.decode()
        today = date.today().isoformat()
        # Hidden input has today
        assert f'id="date-default" value="{today}"' in content
        # Picker has the original date
        assert b'value="2026-03-15"' in response.content


# ---------------------------------------------------------------------------
# Transaction CRUD
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTransactionCRUD:
    def test_create_success(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.post(
            "/transactions",
            {
                "type": "expense",
                "amount": "500",
                "account_id": tx_view_data["egp_id"],
                "category_id": tx_view_data["cat_id"],
                "date": "2026-03-15",
            },
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        assert b"Transaction saved!" in response.content

    def test_create_validation_error(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.post(
            "/transactions",
            {
                "type": "expense",
                "amount": "0",
                "account_id": tx_view_data["egp_id"],
            },
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 400

    def test_edit_form(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        tx_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 200, 'EGP', %s, -200)",
                [
                    tx_id,
                    tx_view_data["user_id"],
                    tx_view_data["egp_id"],
                    date(2026, 3, 15),
                ],
            )
        response = c.get(f"/transactions/edit/{tx_id}", HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        assert b"Save" in response.content

    def test_edit_form_va_hidden_behind_toggle(self, client, tx_view_data):
        # VA toggle only renders when the user has virtual accounts
        va_id = str(uuid.uuid4())
        tx_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO virtual_accounts (id, user_id, name, current_balance, display_order)"
                " VALUES (%s, %s, 'Groceries', 0, 1)",
                [va_id, tx_view_data["user_id"]],
            )
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 200, 'EGP', %s, -200)",
                [
                    tx_id,
                    tx_view_data["user_id"],
                    tx_view_data["egp_id"],
                    date(2026, 3, 15),
                ],
            )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/edit/{tx_id}", HTTP_HX_REQUEST="true")
        content = response.content.decode()
        assert "edit-more-options" in content
        assert 'aria-expanded="false"' in content
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM virtual_accounts WHERE id = %s", [va_id])

    def test_edit_form_no_toggle_without_virtual_accounts(self, client, tx_view_data):
        """No More options toggle when the user has no virtual accounts."""
        tx_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 200, 'EGP', %s, -200)",
                [
                    tx_id,
                    tx_view_data["user_id"],
                    tx_view_data["egp_id"],
                    date(2026, 3, 15),
                ],
            )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/edit/{tx_id}", HTTP_HX_REQUEST="true")
        assert b"edit-more-options" not in response.content
        assert b"More options" not in response.content

    def test_edit_form_auto_expands_when_va_selected(self, client, tx_view_data):
        """JS openEditMore() is rendered when the transaction has a VA allocation."""
        va_id = str(uuid.uuid4())
        tx_id = str(uuid.uuid4())
        alloc_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO virtual_accounts (id, user_id, name, current_balance, display_order)"
                " VALUES (%s, %s, 'Groceries', 0, 1)",
                [va_id, tx_view_data["user_id"]],
            )
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 200, 'EGP', %s, -200)",
                [
                    tx_id,
                    tx_view_data["user_id"],
                    tx_view_data["egp_id"],
                    date(2026, 3, 15),
                ],
            )
            cursor.execute(
                "INSERT INTO virtual_account_allocations (id, transaction_id, virtual_account_id, amount)"
                " VALUES (%s, %s, %s, -200)",
                [alloc_id, tx_id, va_id],
            )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/edit/{tx_id}", HTTP_HX_REQUEST="true")
        # The auto-expand invocation appears after the comment, distinct from the function definition
        assert b"// Auto-expand if a VA is already selected" in response.content
        assert b"openEditMore();" in response.content
        # Confirm it's the conditional call specifically (not just the function body)
        content = response.content.decode()
        auto_expand_block = content.split("// Auto-expand if a VA is already selected")[
            1
        ]
        assert "openEditMore();" in auto_expand_block
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM virtual_account_allocations WHERE id = %s", [alloc_id]
            )
            cursor.execute("DELETE FROM virtual_accounts WHERE id = %s", [va_id])

    def test_edit_form_no_auto_expand_without_va(self, client, tx_view_data):
        """Auto-expand call is absent after the marker comment when no VA is allocated."""
        va_id = str(uuid.uuid4())
        tx_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO virtual_accounts (id, user_id, name, current_balance, display_order)"
                " VALUES (%s, %s, 'Groceries', 0, 1)",
                [va_id, tx_view_data["user_id"]],
            )
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 200, 'EGP', %s, -200)",
                [
                    tx_id,
                    tx_view_data["user_id"],
                    tx_view_data["egp_id"],
                    date(2026, 3, 15),
                ],
            )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/edit/{tx_id}", HTTP_HX_REQUEST="true")
        content = response.content.decode()
        auto_expand_block = content.split("// Auto-expand if a VA is already selected")[
            1
        ]
        assert "openEditMore();" not in auto_expand_block
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM virtual_accounts WHERE id = %s", [va_id])

    def test_update_via_put(self, client, tx_view_data):
        """PUT /transactions/<id> should update the transaction amount."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        tx_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 200, 'EGP', %s, -200)",
                [
                    tx_id,
                    tx_view_data["user_id"],
                    tx_view_data["egp_id"],
                    date(2026, 3, 15),
                ],
            )
            cursor.execute(
                "UPDATE accounts SET current_balance = current_balance - 200 WHERE id = %s",
                [tx_view_data["egp_id"]],
            )
        response = c.put(
            f"/transactions/{tx_id}",
            data="type=expense&amount=300&category_id=&note=Updated&date=2026-03-15",
            content_type="application/x-www-form-urlencoded",
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.content!r}"
        )

    def test_delete(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        tx_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 200, 'EGP', %s, -200)",
                [
                    tx_id,
                    tx_view_data["user_id"],
                    tx_view_data["egp_id"],
                    date(2026, 3, 15),
                ],
            )
            cursor.execute(
                "UPDATE accounts SET current_balance = current_balance - 200 WHERE id = %s",
                [tx_view_data["egp_id"]],
            )
        response = c.delete(f"/transactions/{tx_id}", HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        assert response.content == b""

    def test_row_partial(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        tx_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 200, 'EGP', %s, -200)",
                [
                    tx_id,
                    tx_view_data["user_id"],
                    tx_view_data["egp_id"],
                    date(2026, 3, 15),
                ],
            )
        response = c.get(f"/transactions/row/{tx_id}", HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        assert b"EGP" in response.content


# ---------------------------------------------------------------------------
# Transfer
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTransferViews:
    def test_transfer_new_page(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/transfers/new")
        assert response.status_code == 200
        assert b"Transfer Between Accounts" in response.content

    def test_transfer_create(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        # Create a second account
        dest_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO accounts (id, user_id, institution_id, name, type, currency,"
                " current_balance, initial_balance)"
                " VALUES (%s, %s, (SELECT id FROM institutions WHERE user_id = %s LIMIT 1),"
                " %s, 'savings', 'EGP', %s, %s)",
                [
                    dest_id,
                    tx_view_data["user_id"],
                    tx_view_data["user_id"],
                    "Dest",
                    5000,
                    5000,
                ],
            )
        response = c.post(
            "/transactions/transfer",
            {
                "source_account_id": tx_view_data["egp_id"],
                "dest_account_id": dest_id,
                "amount": "1000",
                "date": "2026-03-15",
            },
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        assert b"Transfer completed!" in response.content


# ---------------------------------------------------------------------------
# Exchange
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestExchangeViews:
    def test_exchange_new_page(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/exchange/new")
        assert response.status_code == 200
        assert b"Currency Exchange" in response.content


# ---------------------------------------------------------------------------
# Batch entry
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestBatchViews:
    def test_batch_entry_page(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/batch-entry")
        assert response.status_code == 200
        assert b"Batch Entry" in response.content


# ---------------------------------------------------------------------------
# Fawry
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestFawryViews:
    def test_fawry_cashout_page(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/fawry-cashout")
        assert response.status_code == 200
        assert b"Fawry" in response.content


# ---------------------------------------------------------------------------
# Quick entry partials
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestQuickEntryViews:
    def test_quick_entry_form(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/transactions/quick-form", HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        assert b"Quick Entry" in response.content

    def test_quick_form_note_has_label(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/transactions/quick-form", HTTP_HX_REQUEST="true")
        content = response.content.decode()
        assert 'for="qe-note-input"' in content
        assert 'id="qe-note-input"' in content

    def test_quick_form_hidden_date_has_today(self, client, tx_view_data):
        """The hidden date input specifically holds today's date."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/transactions/quick-form", HTTP_HX_REQUEST="true")
        content = response.content.decode()
        today = date.today().isoformat()
        assert f'id="qe-date-input" value="{today}"' in content

    def test_quick_form_date_picker_starts_disabled(self, client, tx_view_data):
        """Date picker inside More options must start disabled."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/transactions/quick-form", HTTP_HX_REQUEST="true")
        content = response.content.decode()
        assert 'id="qe-date-picker" disabled' in content

    def test_quick_form_structure(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/transactions/quick-form", HTTP_HX_REQUEST="true")
        content = response.content.decode()
        # Note is visible above the toggle (not inside the panel)
        assert 'name="note"' in content
        note_pos = content.index('name="note"')
        toggle_pos = content.index('id="qe-more-options-toggle"')
        assert note_pos < toggle_pos, (
            "note should appear before the More options toggle"
        )
        # Toggle and panel present
        assert 'id="qe-more-options"' in content
        assert 'aria-expanded="false"' in content
        # Date picker is inside the panel
        today = date.today().isoformat()
        assert f'value="{today}"' in content

    def test_quick_transfer_form(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/transactions/quick-transfer", HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        assert b"Quick Transfer" in response.content

    def test_quick_exchange_form(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/exchange/quick-form", HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        assert b"Quick Exchange" in response.content


# ---------------------------------------------------------------------------
# Sync API
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSyncAPI:
    def test_sync_json(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        payload = [
            {"type": "expense", "amount": 100, "account_id": tx_view_data["egp_id"]},
            {"type": "income", "amount": 200, "account_id": tx_view_data["egp_id"]},
        ]
        response = c.post(
            "/sync/transactions",
            data=json.dumps(payload),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["created"] == 2
        assert data["failed"] == 0


# ---------------------------------------------------------------------------
# Suggest category
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestSuggestCategory:
    def test_returns_text(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/api/transactions/suggest-category?note=test")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Category visible in transaction list rows
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTransactionListShowsCategory:
    """Transaction list page displays category icon and name in each row."""

    def test_category_visible_in_row(self, client, tx_view_data: dict) -> None:
        """Row HTML includes the category icon and name when a category is set."""
        user_id = tx_view_data["user_id"]
        cat_id = str(uuid.uuid4())
        tx_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO categories (id, user_id, name, type, icon)"
                " VALUES (%s, %s, 'Groceries', 'expense', '🍕')",
                [cat_id, user_id],
            )
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount,"
                " currency, date, category_id, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 100, 'EGP', CURRENT_DATE, %s, -100)",
                [tx_id, user_id, tx_view_data["egp_id"], cat_id],
            )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/transactions")
        content = response.content.decode()
        assert "🍕" in content
        assert "Groceries" in content

    def test_category_and_note_combined(self, client, tx_view_data: dict) -> None:
        """Row shows 'Category · Note' when both are present."""
        user_id = tx_view_data["user_id"]
        cat_id = str(uuid.uuid4())
        tx_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO categories (id, user_id, name, type, icon)"
                " VALUES (%s, %s, 'Groceries', 'expense', '🍕')",
                [cat_id, user_id],
            )
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount,"
                " currency, date, category_id, note, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 100, 'EGP', CURRENT_DATE, %s, %s, -100)",
                [tx_id, user_id, tx_view_data["egp_id"], cat_id, "Carrefour"],
            )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/transactions")
        content = response.content.decode()
        assert "Groceries · Carrefour" in content

    def test_no_category_no_separator(self, client, tx_view_data: dict) -> None:
        """Row HTML renders correctly (no dangling separator) when category is null."""
        user_id = tx_view_data["user_id"]
        tx_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount,"
                " currency, date, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 50, 'EGP', CURRENT_DATE, -50)",
                [tx_id, user_id, tx_view_data["egp_id"]],
            )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/transactions")
        assert response.status_code == 200
        # Row renders without a trailing " · " separator after account name
        content = response.content.decode()
        assert "EGP Savings · <" not in content  # no trailing separator

    # gap: functional — category with no icon
    def test_category_without_icon_renders_name_only(
        self, client, tx_view_data: dict
    ) -> None:
        """Category with NULL icon shows just the name — no leading space or placeholder."""
        user_id = tx_view_data["user_id"]
        cat_id = str(uuid.uuid4())
        tx_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO categories (id, user_id, name, type)"  # icon omitted → NULL
                " VALUES (%s, %s, 'Transport', 'expense')",
                [cat_id, user_id],
            )
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount,"
                " currency, date, category_id, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 30, 'EGP', CURRENT_DATE, %s, -30)",
                [tx_id, user_id, tx_view_data["egp_id"], cat_id],
            )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/transactions")
        content = response.content.decode()
        assert "Transport" in content

    # gap: functional — note present, no category
    def test_note_shown_when_no_category(self, client, tx_view_data: dict) -> None:
        """When category is NULL but note is set, row shows only the note."""
        user_id = tx_view_data["user_id"]
        tx_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount,"
                " currency, date, note, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 20, 'EGP', CURRENT_DATE, %s, -20)",
                [tx_id, user_id, tx_view_data["egp_id"], "Uber ride"],
            )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/transactions")
        content = response.content.decode()
        assert "Uber ride" in content

    # gap: functional — type fallback explicit assertion
    def test_type_fallback_when_no_category_no_note(
        self, client, tx_view_data: dict
    ) -> None:
        """When both category and note are absent, row falls back to the type label."""
        user_id = tx_view_data["user_id"]
        tx_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount,"
                " currency, date, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 15, 'EGP', CURRENT_DATE, -15)",
                [tx_id, user_id, tx_view_data["egp_id"]],
            )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/transactions")
        content = response.content.decode()
        assert "Expense" in content  # format_type('expense') → 'Expense'

    def test_empty_string_note_falls_back_to_category(
        self, client, tx_view_data: dict
    ) -> None:
        """Empty-string note is treated as absent — category icon+name is shown instead."""
        user_id = tx_view_data["user_id"]
        cat_id = str(uuid.uuid4())
        tx_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO categories (id, user_id, name, type, icon)"
                " VALUES (%s, %s, 'Transport', 'expense', '🚗')",
                [cat_id, user_id],
            )
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount,"
                " currency, date, category_id, note, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 40, 'EGP', CURRENT_DATE, %s, '', -40)",
                [tx_id, user_id, tx_view_data["egp_id"], cat_id],
            )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/transactions")
        content = response.content.decode()
        assert "🚗" in content
        assert "Transport" in content

    # gap: functional — category with no icon + note present
    def test_category_without_icon_and_with_note(
        self, client, tx_view_data: dict
    ) -> None:
        """Category with NULL icon + note renders as 'Category · Note' (no icon prefix)."""
        user_id = tx_view_data["user_id"]
        cat_id = str(uuid.uuid4())
        tx_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO categories (id, user_id, name, type)"  # icon omitted → NULL
                " VALUES (%s, %s, 'Transport', 'expense')",
                [cat_id, user_id],
            )
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount,"
                " currency, date, category_id, note, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 45, 'EGP', CURRENT_DATE, %s, %s, -45)",
                [tx_id, user_id, tx_view_data["egp_id"], cat_id, "Uber"],
            )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/transactions")
        content = response.content.decode()
        assert "Transport · Uber" in content

    # gap: functional — account name shown in list rows (not hide_account_name path)
    def test_transaction_row_shows_account_name_in_list(
        self, client, tx_view_data: dict
    ) -> None:
        """Transaction list rows include the account name in the secondary info line."""
        user_id = tx_view_data["user_id"]
        tx_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount,"
                " currency, date, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 10, 'EGP', CURRENT_DATE, -10)",
                [tx_id, user_id, tx_view_data["egp_id"]],
            )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/transactions")
        content = response.content.decode()
        assert "· EGP Savings" in content


# ---------------------------------------------------------------------------
# Edit response row contains category (gap: functional)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTransactionEditResponseShowsCategory:
    """PUT /transactions/<id> returns updated row HTML that includes category."""

    def test_edit_response_row_shows_category(self, client, tx_view_data: dict) -> None:
        # gap: functional — edit response row
        user_id = tx_view_data["user_id"]
        cat_id = str(uuid.uuid4())
        tx_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO categories (id, user_id, name, type, icon)"
                " VALUES (%s, %s, 'Dining', 'expense', '🍽️')",
                [cat_id, user_id],
            )
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount,"
                " currency, date, category_id, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 200, 'EGP', CURRENT_DATE, %s, -200)",
                [tx_id, user_id, tx_view_data["egp_id"], cat_id],
            )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.put(
            f"/transactions/{tx_id}",
            data=f"type=expense&amount=200&category_id={cat_id}&note=Pasta&date=2026-03-24",
            content_type="application/x-www-form-urlencoded",
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "Dining" in content
        assert "Pasta" in content
        assert "Dining · Pasta" in content


# ---------------------------------------------------------------------------
# Transaction detail sheet (bottom sheet partial)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTransactionDetailSheet:
    """GET /transactions/detail/<id> returns a bottom-sheet detail partial."""

    def test_returns_200_with_detail_content(self, client, tx_view_data):
        tx_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount,"
                " currency, date, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 500, 'EGP', %s, -500)",
                [
                    tx_id,
                    tx_view_data["user_id"],
                    tx_view_data["egp_id"],
                    date(2026, 3, 15),
                ],
            )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/detail/{tx_id}")
        assert response.status_code == 200
        content = response.content.decode()
        assert "500" in content
        assert "EGP Savings" in content

    def test_404_for_nonexistent_id(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/detail/{uuid.uuid4()}")
        assert response.status_code == 404

    def test_404_for_other_users_tx(self, client, tx_view_data):
        other_user = UserFactory()
        SessionFactory(user=other_user)
        other_inst_id = str(uuid.uuid4())
        other_acct_id = str(uuid.uuid4())
        tx_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO institutions (id, user_id, name, type)"
                " VALUES (%s, %s, %s, 'bank')",
                [other_inst_id, str(other_user.id), "Other Bank"],
            )
            cursor.execute(
                "INSERT INTO accounts (id, user_id, institution_id, name, type,"
                " currency, current_balance, initial_balance)"
                " VALUES (%s, %s, %s, 'Other Acct', 'savings', 'EGP', 5000, 5000)",
                [other_acct_id, str(other_user.id), other_inst_id],
            )
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount,"
                " currency, date, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 300, 'EGP', %s, -300)",
                [tx_id, str(other_user.id), other_acct_id, date(2026, 3, 15)],
            )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/detail/{tx_id}")
        assert response.status_code == 404
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM transactions WHERE id = %s", [tx_id])
            cursor.execute("DELETE FROM accounts WHERE id = %s", [other_acct_id])
            cursor.execute("DELETE FROM institutions WHERE id = %s", [other_inst_id])
        Session.objects.filter(user=other_user).delete()
        User.objects.filter(id=other_user.id).delete()

    def test_unauthenticated_redirects(self, client):
        response = client.get(f"/transactions/detail/{uuid.uuid4()}")
        assert response.status_code == 302
        assert "/login" in response.url

    def test_shows_category_name_and_icon(self, client, tx_view_data):
        cat_id = str(uuid.uuid4())
        tx_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO categories (id, user_id, name, type, icon)"
                " VALUES (%s, %s, 'Dining', 'expense', '🍽️')",
                [cat_id, tx_view_data["user_id"]],
            )
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount,"
                " currency, date, category_id, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 150, 'EGP', %s, %s, -150)",
                [
                    tx_id,
                    tx_view_data["user_id"],
                    tx_view_data["egp_id"],
                    date(2026, 3, 15),
                    cat_id,
                ],
            )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/detail/{tx_id}")
        content = response.content.decode()
        assert "Dining" in content
        assert "\U0001f37d\ufe0f" in content  # 🍽️
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM transactions WHERE id = %s", [tx_id])
            cursor.execute("DELETE FROM categories WHERE id = %s", [cat_id])

    def test_shows_transfer_counter_account(self, client, tx_view_data):
        acct2_id = str(uuid.uuid4())
        tx1_id = str(uuid.uuid4())
        tx2_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO accounts (id, user_id, institution_id, name, type,"
                " currency, current_balance, initial_balance)"
                " VALUES (%s, %s,"
                " (SELECT id FROM institutions WHERE user_id = %s LIMIT 1),"
                " 'USD Savings', 'savings', 'USD', 5000, 5000)",
                [acct2_id, tx_view_data["user_id"], tx_view_data["user_id"]],
            )
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id,"
                " counter_account_id, type, amount, currency, date,"
                " balance_delta, linked_transaction_id)"
                " VALUES (%s, %s, %s, %s, 'transfer', 1000, 'EGP', %s, -1000, %s)",
                [
                    tx1_id,
                    tx_view_data["user_id"],
                    tx_view_data["egp_id"],
                    acct2_id,
                    date(2026, 3, 15),
                    tx2_id,
                ],
            )
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id,"
                " counter_account_id, type, amount, currency, date,"
                " balance_delta, linked_transaction_id)"
                " VALUES (%s, %s, %s, %s, 'transfer', 1000, 'USD', %s, 1000, %s)",
                [
                    tx2_id,
                    tx_view_data["user_id"],
                    acct2_id,
                    tx_view_data["egp_id"],
                    date(2026, 3, 15),
                    tx1_id,
                ],
            )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/detail/{tx1_id}")
        content = response.content.decode()
        assert "USD Savings" in content
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM transactions WHERE id IN (%s, %s)", [tx1_id, tx2_id]
            )
            cursor.execute("DELETE FROM accounts WHERE id = %s", [acct2_id])

    def test_shows_virtual_account_allocation(self, client, tx_view_data):
        va_id = str(uuid.uuid4())
        tx_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO virtual_accounts"
                " (id, user_id, name, current_balance, display_order)"
                " VALUES (%s, %s, 'Groceries Fund', 0, 1)",
                [va_id, tx_view_data["user_id"]],
            )
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount,"
                " currency, date, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 200, 'EGP', %s, -200)",
                [
                    tx_id,
                    tx_view_data["user_id"],
                    tx_view_data["egp_id"],
                    date(2026, 3, 15),
                ],
            )
            cursor.execute(
                "INSERT INTO virtual_account_allocations"
                " (id, virtual_account_id, transaction_id, amount)"
                " VALUES (%s, %s, %s, -200)",
                [str(uuid.uuid4()), va_id, tx_id],
            )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/detail/{tx_id}")
        content = response.content.decode()
        assert "Groceries Fund" in content
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM virtual_account_allocations WHERE transaction_id = %s",
                [tx_id],
            )
            cursor.execute("DELETE FROM transactions WHERE id = %s", [tx_id])
            cursor.execute("DELETE FROM virtual_accounts WHERE id = %s", [va_id])

    def test_shows_edit_and_delete_buttons(self, client, tx_view_data):
        tx_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount,"
                " currency, date, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 100, 'EGP', %s, -100)",
                [
                    tx_id,
                    tx_view_data["user_id"],
                    tx_view_data["egp_id"],
                    date(2026, 3, 15),
                ],
            )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/detail/{tx_id}")
        content = response.content.decode()
        assert "Edit" in content
        assert "Delete" in content
        assert f"/transactions/edit/{tx_id}" in content
        assert "hx-delete" in content

    def test_income_shows_plus_sign(self, client, tx_view_data):
        # gap: functional — income amount sign and color
        tx_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount,"
                " currency, date, balance_delta)"
                " VALUES (%s, %s, %s, 'income', 250, 'EGP', %s, 250)",
                [
                    tx_id,
                    tx_view_data["user_id"],
                    tx_view_data["egp_id"],
                    date(2026, 3, 15),
                ],
            )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/detail/{tx_id}")
        content = response.content.decode()
        assert "+EGP" in content or "+$" in content or ("+EGP" in content)
        assert "text-green-600" in content
        assert "Income" in content

    def test_transfer_from_label_on_credit_leg(self, client, tx_view_data):
        # gap: functional — transfer direction label for incoming
        acct2_id = str(uuid.uuid4())
        tx1_id = str(uuid.uuid4())
        tx2_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO accounts (id, user_id, institution_id, name, type,"
                " currency, current_balance, initial_balance)"
                " VALUES (%s, %s,"
                " (SELECT id FROM institutions WHERE user_id = %s LIMIT 1),"
                " 'Savings', 'savings', 'EGP', 5000, 5000)",
                [acct2_id, tx_view_data["user_id"], tx_view_data["user_id"]],
            )
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id,"
                " counter_account_id, type, amount, currency, date,"
                " balance_delta, linked_transaction_id)"
                " VALUES (%s, %s, %s, %s, 'transfer', 500, 'EGP', %s, -500, %s)",
                [
                    tx1_id,
                    tx_view_data["user_id"],
                    tx_view_data["egp_id"],
                    acct2_id,
                    date(2026, 3, 15),
                    tx2_id,
                ],
            )
            # Credit leg — this is the one we'll check
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id,"
                " counter_account_id, type, amount, currency, date,"
                " balance_delta, linked_transaction_id)"
                " VALUES (%s, %s, %s, %s, 'transfer', 500, 'EGP', %s, 500, %s)",
                [
                    tx2_id,
                    tx_view_data["user_id"],
                    acct2_id,
                    tx_view_data["egp_id"],
                    date(2026, 3, 15),
                    tx1_id,
                ],
            )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/detail/{tx2_id}")
        content = response.content.decode()
        assert "Transfer from" in content
        assert "EGP Savings" in content
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM transactions WHERE id IN (%s, %s)", [tx1_id, tx2_id]
            )
            cursor.execute("DELETE FROM accounts WHERE id = %s", [acct2_id])

    def test_no_category_hides_category_row(self, client, tx_view_data):
        # gap: functional — category absent branch
        tx_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount,"
                " currency, date, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 100, 'EGP', %s, -100)",
                [
                    tx_id,
                    tx_view_data["user_id"],
                    tx_view_data["egp_id"],
                    date(2026, 3, 15),
                ],
            )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/detail/{tx_id}")
        content = response.content.decode()
        # "Category" label should not appear when no category set
        assert ">Category<" not in content

    def test_empty_note_hides_note_row(self, client, tx_view_data):
        # gap: data — empty string note
        tx_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount,"
                " currency, date, note, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 100, 'EGP', %s, '', -100)",
                [
                    tx_id,
                    tx_view_data["user_id"],
                    tx_view_data["egp_id"],
                    date(2026, 3, 15),
                ],
            )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/detail/{tx_id}")
        content = response.content.decode()
        assert ">Note<" not in content

    def test_shows_tags(self, client, tx_view_data):
        # gap: data — tags display
        tx_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount,"
                " currency, date, tags, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 100, 'EGP', %s,"
                " '{food,lunch}', -100)",
                [
                    tx_id,
                    tx_view_data["user_id"],
                    tx_view_data["egp_id"],
                    date(2026, 3, 15),
                ],
            )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/detail/{tx_id}")
        content = response.content.decode()
        assert "food" in content
        assert "lunch" in content
        assert "Tags" in content

    def test_exchange_counter_amount_uses_counter_currency(self, client, tx_view_data):
        # gap: data — cross-currency exchange shows counter_amount in counter account's currency
        acct2_id = str(uuid.uuid4())
        tx1_id = str(uuid.uuid4())
        tx2_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO accounts (id, user_id, institution_id, name, type,"
                " currency, current_balance, initial_balance)"
                " VALUES (%s, %s,"
                " (SELECT id FROM institutions WHERE user_id = %s LIMIT 1),"
                " 'USD Account', 'savings', 'USD', 500, 500)",
                [acct2_id, tx_view_data["user_id"], tx_view_data["user_id"]],
            )
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id,"
                " counter_account_id, type, amount, currency, date,"
                " balance_delta, linked_transaction_id,"
                " exchange_rate, counter_amount)"
                " VALUES (%s, %s, %s, %s, 'exchange', 5000, 'EGP', %s, -5000, %s, 50.0, 100.0)",
                [
                    tx1_id,
                    tx_view_data["user_id"],
                    tx_view_data["egp_id"],
                    acct2_id,
                    date(2026, 3, 15),
                    tx2_id,
                ],
            )
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id,"
                " counter_account_id, type, amount, currency, date,"
                " balance_delta, linked_transaction_id)"
                " VALUES (%s, %s, %s, %s, 'exchange', 100, 'USD', %s, 100, %s)",
                [
                    tx2_id,
                    tx_view_data["user_id"],
                    acct2_id,
                    tx_view_data["egp_id"],
                    date(2026, 3, 15),
                    tx1_id,
                ],
            )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/detail/{tx1_id}")
        content = response.content.decode()
        # counter_amount should be shown in USD (counter account currency), not EGP
        assert "$100" in content or "USD" in content
        assert "Counter amount" in content
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM transactions WHERE id IN (%s, %s)", [tx1_id, tx2_id]
            )
            cursor.execute("DELETE FROM accounts WHERE id = %s", [acct2_id])

    def test_counter_amount_hidden_when_counter_account_deleted(
        self, client, tx_view_data
    ):
        # gap: data — counter_amount must not render with wrong currency when counter account gone
        # counter_currency will be missing from context → format_currency defaults to EGP (wrong)
        # The fix: guard {% if tx.counter_amount %} with counter_currency too
        acct2_id = str(uuid.uuid4())
        tx_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO accounts (id, user_id, institution_id, name, type,"
                " currency, current_balance, initial_balance)"
                " VALUES (%s, %s,"
                " (SELECT id FROM institutions WHERE user_id = %s LIMIT 1),"
                " 'Temp USD', 'savings', 'USD', 500, 500)",
                [acct2_id, tx_view_data["user_id"], tx_view_data["user_id"]],
            )
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id,"
                " counter_account_id, type, amount, currency, date,"
                " balance_delta, exchange_rate, counter_amount)"
                " VALUES (%s, %s, %s, %s, 'exchange', 5000, 'EGP', %s, -5000, 50.0, 100.0)",
                [
                    tx_id,
                    tx_view_data["user_id"],
                    tx_view_data["egp_id"],
                    acct2_id,
                    date(2026, 3, 15),
                ],
            )
            # Delete the counter account (simulating a deleted account scenario)
            cursor.execute("DELETE FROM accounts WHERE id = %s", [acct2_id])
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/detail/{tx_id}")
        assert response.status_code == 200
        content = response.content.decode()
        # counter_amount must NOT appear with wrong EGP default when counter account is gone
        assert "Counter amount" not in content
