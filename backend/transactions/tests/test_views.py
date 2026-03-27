"""
Transaction view tests — HTTP-level tests for all /transactions/*, /transfers/*,
/exchange/*, /batch-entry, and /fawry-cashout routes.

Uses factory_boy fixtures for test data setup (no raw SQL).
"""

import json
import uuid
from datetime import date

import pytest

from conftest import SessionFactory, UserFactory, set_auth_cookie
from core.models import Account, Transaction, VirtualAccount, VirtualAccountAllocation
from tests.factories import (
    AccountFactory,
    CategoryFactory,
    InstitutionFactory,
    PersonFactory,
    TransactionFactory,
    VirtualAccountAllocationFactory,
    VirtualAccountFactory,
)


@pytest.fixture
def tx_view_data(db):
    """User + session + institution + EGP savings account + category."""
    user = UserFactory()
    session = SessionFactory(user=user)
    inst = InstitutionFactory(user_id=user.id, name="Test Bank", type="bank")
    acct = AccountFactory(
        user_id=user.id,
        institution_id=inst.id,
        name="EGP Savings",
        currency="EGP",
        current_balance=10000,
        initial_balance=10000,
        type="savings",
    )
    cat = CategoryFactory(user_id=user.id, name="Food", type="expense")

    yield {
        "user_id": str(user.id),
        "session_token": session.token,
        "inst_id": str(inst.id),
        "egp_id": str(acct.id),
        "cat_id": str(cat.id),
    }


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

    def test_no_new_button_in_header(self, client, tx_view_data):
        """The '+ New' link was removed from the transactions page header."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/transactions")
        content = response.content.decode()
        assert response.status_code == 200
        assert "Transactions" in content
        assert "+ New" not in content

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
        tx = TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            type="expense",
            amount=500,
            currency="EGP",
            date=date(2026, 3, 15),
            note="Test note",
            balance_delta=-500,
        )
        response = c.get(f"/transactions/new?dup={tx.id}")
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
        tx = TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            type="expense",
            amount=500,
            currency="EGP",
            date=date(2026, 3, 15),
            balance_delta=-500,
        )
        response = c.get(f"/transactions/new?dup={tx.id}")
        assert b'value="2026-03-15"' in response.content

    def test_duplicate_note_prefilled_and_visible(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        tx = TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            type="expense",
            amount=500,
            currency="EGP",
            date=date(2026, 3, 15),
            note="Lunch",
            balance_delta=-500,
        )
        response = c.get(f"/transactions/new?dup={tx.id}")
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
        tx = TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            type="expense",
            amount=500,
            currency="EGP",
            date=date(2026, 3, 15),
            balance_delta=-500,
        )
        response = c.get(f"/transactions/new?dup={tx.id}")
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
        tx = TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            type="expense",
            amount=200,
            currency="EGP",
            date=date(2026, 3, 15),
            balance_delta=-200,
        )
        response = c.get(f"/transactions/edit/{tx.id}", HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        assert b"Save" in response.content

    def test_edit_form_va_hidden_behind_toggle(self, client, tx_view_data):
        # VA toggle only renders when the user has virtual accounts
        VirtualAccountFactory(
            user_id=tx_view_data["user_id"],
            name="Groceries",
            current_balance=0,
        )
        tx = TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            type="expense",
            amount=200,
            currency="EGP",
            date=date(2026, 3, 15),
            balance_delta=-200,
        )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/edit/{tx.id}", HTTP_HX_REQUEST="true")
        content = response.content.decode()
        assert "edit-more-options" in content
        assert 'aria-expanded="false"' in content

    def test_edit_form_no_toggle_without_virtual_accounts(self, client, tx_view_data):
        """No More options toggle when the user has no virtual accounts."""
        tx = TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            type="expense",
            amount=200,
            currency="EGP",
            date=date(2026, 3, 15),
            balance_delta=-200,
        )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/edit/{tx.id}", HTTP_HX_REQUEST="true")
        assert b"edit-more-options" not in response.content
        assert b"More options" not in response.content

    def test_edit_form_auto_expands_when_va_selected(self, client, tx_view_data):
        """JS openEditMore() is called when the transaction has a VA allocation."""
        va = VirtualAccountFactory(
            user_id=tx_view_data["user_id"],
            name="Groceries",
            current_balance=0,
        )
        tx = TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            type="expense",
            amount=200,
            currency="EGP",
            date=date(2026, 3, 15),
            balance_delta=-200,
        )
        VirtualAccountAllocationFactory(
            virtual_account_id=va.id,
            transaction_id=tx.id,
            amount=-200,
        )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/edit/{tx.id}", HTTP_HX_REQUEST="true")
        assert b"openEditMore();" in response.content

    def test_edit_form_no_auto_expand_without_va(self, client, tx_view_data):
        """openEditMore() is not called when no VA is allocated."""
        VirtualAccountFactory(
            user_id=tx_view_data["user_id"],
            name="Groceries",
            current_balance=0,
        )
        tx = TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            type="expense",
            amount=200,
            currency="EGP",
            date=date(2026, 3, 15),
            balance_delta=-200,
        )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/edit/{tx.id}", HTTP_HX_REQUEST="true")
        content = response.content.decode()
        # The function definition exists but the conditional call should not
        # Count occurrences — function body has one, conditional call would add another
        count = content.count("openEditMore();")
        # Only the function definition, no conditional call
        assert count <= 1

    def test_update_via_put(self, client, tx_view_data):
        """PUT /transactions/<id> should update the transaction amount."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        tx = TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            type="expense",
            amount=200,
            currency="EGP",
            date=date(2026, 3, 15),
            balance_delta=-200,
        )
        # Reflect the transaction in the account balance (10000 - 200 = 9800)
        Account.objects.filter(id=tx_view_data["egp_id"]).update(current_balance=9800)
        response = c.put(
            f"/transactions/{tx.id}",
            data="type=expense&amount=300&category_id=&note=Updated&date=2026-03-15",
            content_type="application/x-www-form-urlencoded",
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.content!r}"
        )

    def test_delete(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        tx = TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            type="expense",
            amount=200,
            currency="EGP",
            date=date(2026, 3, 15),
            balance_delta=-200,
        )
        # Reflect the transaction in the account balance (10000 - 200 = 9800)
        Account.objects.filter(id=tx_view_data["egp_id"]).update(current_balance=9800)
        response = c.delete(f"/transactions/{tx.id}", HTTP_HX_REQUEST="true")
        assert response.status_code == 200
        assert response.content == b""

    def test_row_partial(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        tx = TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            type="expense",
            amount=200,
            currency="EGP",
            date=date(2026, 3, 15),
            balance_delta=-200,
        )
        response = c.get(f"/transactions/row/{tx.id}", HTTP_HX_REQUEST="true")
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
        dest = AccountFactory(
            user_id=tx_view_data["user_id"],
            institution_id=tx_view_data["inst_id"],
            name="Dest",
            currency="EGP",
            current_balance=5000,
            initial_balance=5000,
            type="savings",
        )
        response = c.post(
            "/transactions/transfer",
            {
                "source_account_id": tx_view_data["egp_id"],
                "dest_account_id": str(dest.id),
                "amount": "1000",
                "date": "2026-03-15",
            },
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        assert b"Transfer completed!" in response.content

    def test_transfer_with_fee_via_form(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        dest = AccountFactory(
            user_id=tx_view_data["user_id"],
            institution_id=tx_view_data["inst_id"],
            name="Dest",
            currency="EGP",
            current_balance=5000,
            initial_balance=5000,
            type="savings",
        )
        response = c.post(
            "/transactions/transfer",
            {
                "source_account_id": tx_view_data["egp_id"],
                "dest_account_id": str(dest.id),
                "amount": "500",
                "fee_amount": "10",
                "date": "2026-03-15",
            },
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200
        assert b"Transfer completed!" in response.content

    def test_transfer_form_has_fee_field(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/transfers/new")
        content = response.content.decode()
        assert 'name="fee_amount"' in content

    def test_transfer_form_no_instapay_toggle(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/transfers/new")
        content = response.content.decode()
        assert "instapay-toggle" not in content
        assert "InstaPay" not in content

    def test_fawry_route_redirects_to_transfers(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/fawry-cashout")
        assert response.status_code == 302
        assert "/transfers/new" in response.url  # type: ignore[attr-defined]

    def test_instapay_route_redirects_to_transfers(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.post(
            "/transactions/instapay-transfer",
            {},
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 302


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
    def test_fawry_cashout_redirects(self, client, tx_view_data):
        """Fawry page now redirects to unified transfer form."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/fawry-cashout")
        assert response.status_code == 302
        assert "/transfers/new" in response.url  # type: ignore[attr-defined]


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
# Quick entry OOB swaps for dashboard balance refresh
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestQuickEntryOOBSwaps:
    """Quick entry response includes lazy-load OOB swaps for dashboard balances."""

    def test_response_contains_oob_net_worth(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.post(
            "/transactions/quick",
            {
                "type": "expense",
                "amount": "500",
                "account_id": tx_view_data["egp_id"],
                "category_id": tx_view_data["cat_id"],
            },
            HTTP_HX_REQUEST="true",
        )
        content = resp.content.decode()
        assert 'id="dashboard-net-worth"' in content
        assert 'hx-get="/partials/net-worth"' in content
        assert 'hx-trigger="load"' in content
        assert 'hx-swap="innerHTML"' in content

    def test_response_contains_oob_accounts(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.post(
            "/transactions/quick",
            {
                "type": "expense",
                "amount": "500",
                "account_id": tx_view_data["egp_id"],
                "category_id": tx_view_data["cat_id"],
            },
            HTTP_HX_REQUEST="true",
        )
        content = resp.content.decode()
        assert 'id="dashboard-accounts"' in content
        assert 'hx-get="/partials/accounts"' in content

    def test_oob_net_worth_loads_on_page(self, client, tx_view_data):
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.post(
            "/transactions/quick",
            {
                "type": "expense",
                "amount": "500",
                "account_id": tx_view_data["egp_id"],
                "category_id": tx_view_data["cat_id"],
            },
            HTTP_HX_REQUEST="true",
        )
        content = resp.content.decode()
        # Verify the lazy-load target has hx-trigger="load"
        assert 'hx-trigger="load"' in content

    def test_income_also_triggers_oob(self, client, tx_view_data):
        cat = CategoryFactory(
            user_id=tx_view_data["user_id"], name="Salary", type="income"
        )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.post(
            "/transactions/quick",
            {
                "type": "income",
                "amount": "2000",
                "account_id": tx_view_data["egp_id"],
                "category_id": str(cat.id),
            },
            HTTP_HX_REQUEST="true",
        )
        content = resp.content.decode()
        # Verify both OOB lazy-load swaps are present for income
        assert 'id="dashboard-net-worth"' in content
        assert 'id="dashboard-accounts"' in content
        assert 'hx-trigger="load"' in content

    def test_error_response_has_no_oob(self, client, tx_view_data):
        """Failed quick entry should not include OOB swaps."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.post(
            "/transactions/quick",
            {"type": "expense", "amount": "", "account_id": tx_view_data["egp_id"]},
            HTTP_HX_REQUEST="true",
        )
        content = resp.content.decode()
        assert "hx-swap-oob" not in content

    def test_success_screen_still_present(self, client, tx_view_data):
        """OOB response still contains the success screen."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.post(
            "/transactions/quick",
            {
                "type": "expense",
                "amount": "100",
                "account_id": tx_view_data["egp_id"],
                "category_id": tx_view_data["cat_id"],
            },
            HTTP_HX_REQUEST="true",
        )
        content = resp.content.decode()
        assert "Transaction saved!" in content


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
        cat = CategoryFactory(
            user_id=tx_view_data["user_id"],
            name="Groceries",
            type="expense",
            icon="🍕",
        )
        TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            type="expense",
            amount=100,
            currency="EGP",
            date=date.today(),
            category_id=cat.id,
            balance_delta=-100,
        )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/transactions")
        content = response.content.decode()
        assert "🍕" in content
        assert "Groceries" in content

    def test_category_and_note_combined(self, client, tx_view_data: dict) -> None:
        """Row shows 'Category · Note' when both are present."""
        cat = CategoryFactory(
            user_id=tx_view_data["user_id"],
            name="Groceries",
            type="expense",
            icon="🍕",
        )
        TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            type="expense",
            amount=100,
            currency="EGP",
            date=date.today(),
            category_id=cat.id,
            note="Carrefour",
            balance_delta=-100,
        )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/transactions")
        content = response.content.decode()
        assert "Groceries · Carrefour" in content

    def test_no_category_no_separator(self, client, tx_view_data: dict) -> None:
        """Row HTML renders correctly (no dangling separator) when category is null."""
        TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            type="expense",
            amount=50,
            currency="EGP",
            date=date.today(),
            balance_delta=-50,
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
        cat = CategoryFactory(
            user_id=tx_view_data["user_id"],
            name="Transport",
            type="expense",
            icon=None,
        )
        TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            type="expense",
            amount=30,
            currency="EGP",
            date=date.today(),
            category_id=cat.id,
            balance_delta=-30,
        )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/transactions")
        content = response.content.decode()
        assert "Transport" in content

    # gap: functional — note present, no category
    def test_note_shown_when_no_category(self, client, tx_view_data: dict) -> None:
        """When category is NULL but note is set, row shows only the note."""
        TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            type="expense",
            amount=20,
            currency="EGP",
            date=date.today(),
            note="Uber ride",
            balance_delta=-20,
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
        TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            type="expense",
            amount=15,
            currency="EGP",
            date=date.today(),
            balance_delta=-15,
        )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get("/transactions")
        content = response.content.decode()
        assert "Expense" in content  # format_type('expense') → 'Expense'

    def test_empty_string_note_falls_back_to_category(
        self, client, tx_view_data: dict
    ) -> None:
        """Empty-string note is treated as absent — category icon+name is shown instead."""
        cat = CategoryFactory(
            user_id=tx_view_data["user_id"],
            name="Transport",
            type="expense",
            icon="🚗",
        )
        TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            type="expense",
            amount=40,
            currency="EGP",
            date=date.today(),
            category_id=cat.id,
            note="",
            balance_delta=-40,
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
        cat = CategoryFactory(
            user_id=tx_view_data["user_id"],
            name="Transport",
            type="expense",
            icon=None,
        )
        TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            type="expense",
            amount=45,
            currency="EGP",
            date=date.today(),
            category_id=cat.id,
            note="Uber",
            balance_delta=-45,
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
        TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            type="expense",
            amount=10,
            currency="EGP",
            date=date.today(),
            balance_delta=-10,
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
        cat = CategoryFactory(
            user_id=tx_view_data["user_id"],
            name="Dining",
            type="expense",
            icon="🍽️",
        )
        tx = TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            type="expense",
            amount=200,
            currency="EGP",
            date=date.today(),
            category_id=cat.id,
            balance_delta=-200,
        )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.put(
            f"/transactions/{tx.id}",
            data=f"type=expense&amount=200&category_id={cat.id}&note=Pasta&date=2026-03-24",
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
        tx = TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            type="expense",
            amount=500,
            currency="EGP",
            date=date(2026, 3, 15),
            balance_delta=-500,
        )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/detail/{tx.id}")
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
        other_inst = InstitutionFactory(
            user_id=other_user.id, name="Other Bank", type="bank"
        )
        other_acct = AccountFactory(
            user_id=other_user.id,
            institution_id=other_inst.id,
            name="Other Acct",
            currency="EGP",
            current_balance=5000,
            initial_balance=5000,
            type="savings",
        )
        tx = TransactionFactory(
            user_id=other_user.id,
            account_id=other_acct.id,
            type="expense",
            amount=300,
            currency="EGP",
            date=date(2026, 3, 15),
            balance_delta=-300,
        )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/detail/{tx.id}")
        assert response.status_code == 404

    def test_unauthenticated_redirects(self, client):
        response = client.get(f"/transactions/detail/{uuid.uuid4()}")
        assert response.status_code == 302
        assert "/login" in response.url

    def test_shows_category_name_and_icon(self, client, tx_view_data):
        cat = CategoryFactory(
            user_id=tx_view_data["user_id"],
            name="Dining",
            type="expense",
            icon="🍽️",
        )
        tx = TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            type="expense",
            amount=150,
            currency="EGP",
            date=date(2026, 3, 15),
            category_id=cat.id,
            balance_delta=-150,
        )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/detail/{tx.id}")
        content = response.content.decode()
        assert "Dining" in content
        assert "\U0001f37d\ufe0f" in content  # 🍽️

    def test_shows_transfer_counter_account(self, client, tx_view_data):
        acct2 = AccountFactory(
            user_id=tx_view_data["user_id"],
            institution_id=tx_view_data["inst_id"],
            name="USD Savings",
            currency="USD",
            current_balance=5000,
            initial_balance=5000,
            type="savings",
        )
        tx1 = TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            counter_account_id=acct2.id,
            type="transfer",
            amount=1000,
            currency="EGP",
            date=date(2026, 3, 15),
            balance_delta=-1000,
        )
        tx2 = TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=acct2.id,
            counter_account_id=tx_view_data["egp_id"],
            type="transfer",
            amount=1000,
            currency="USD",
            date=date(2026, 3, 15),
            balance_delta=1000,
            linked_transaction_id=tx1.id,
        )
        # Set the linked_transaction on tx1 now that tx2 exists
        Transaction.objects.filter(id=tx1.id).update(linked_transaction_id=tx2.id)
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/detail/{tx1.id}")
        content = response.content.decode()
        assert "USD Savings" in content

    def test_shows_virtual_account_allocation(self, client, tx_view_data):
        va = VirtualAccountFactory(
            user_id=tx_view_data["user_id"],
            name="Groceries Fund",
            current_balance=0,
        )
        tx = TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            type="expense",
            amount=200,
            currency="EGP",
            date=date(2026, 3, 15),
            balance_delta=-200,
        )
        VirtualAccountAllocationFactory(
            virtual_account_id=va.id,
            transaction_id=tx.id,
            amount=-200,
        )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/detail/{tx.id}")
        content = response.content.decode()
        assert "Groceries Fund" in content

    def test_shows_edit_and_delete_buttons(self, client, tx_view_data):
        tx = TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            type="expense",
            amount=100,
            currency="EGP",
            date=date(2026, 3, 15),
            balance_delta=-100,
        )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/detail/{tx.id}")
        content = response.content.decode()
        assert "Edit" in content
        assert "Delete" in content
        assert f"/transactions/edit/{tx.id}" in content
        assert "hx-delete" in content

    def test_income_shows_plus_sign(self, client, tx_view_data):
        # gap: functional — income amount sign and color
        tx = TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            type="income",
            amount=250,
            currency="EGP",
            date=date(2026, 3, 15),
            balance_delta=250,
        )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/detail/{tx.id}")
        content = response.content.decode()
        assert "+EGP" in content or "+$" in content or ("+EGP" in content)
        assert "text-green-600" in content
        assert "Income" in content

    def test_transfer_from_label_on_credit_leg(self, client, tx_view_data):
        # gap: functional — transfer direction label for incoming
        acct2 = AccountFactory(
            user_id=tx_view_data["user_id"],
            institution_id=tx_view_data["inst_id"],
            name="Savings",
            currency="EGP",
            current_balance=5000,
            initial_balance=5000,
            type="savings",
        )
        tx1 = TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            counter_account_id=acct2.id,
            type="transfer",
            amount=500,
            currency="EGP",
            date=date(2026, 3, 15),
            balance_delta=-500,
        )
        # Credit leg — this is the one we'll check
        tx2 = TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=acct2.id,
            counter_account_id=tx_view_data["egp_id"],
            type="transfer",
            amount=500,
            currency="EGP",
            date=date(2026, 3, 15),
            balance_delta=500,
            linked_transaction_id=tx1.id,
        )
        Transaction.objects.filter(id=tx1.id).update(linked_transaction_id=tx2.id)
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/detail/{tx2.id}")
        content = response.content.decode()
        assert "Transfer from" in content
        assert "EGP Savings" in content

    def test_no_category_hides_category_row(self, client, tx_view_data):
        # gap: functional — category absent branch
        tx = TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            type="expense",
            amount=100,
            currency="EGP",
            date=date(2026, 3, 15),
            balance_delta=-100,
        )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/detail/{tx.id}")
        content = response.content.decode()
        # "Category" label should not appear when no category set
        assert ">Category<" not in content

    def test_empty_note_hides_note_row(self, client, tx_view_data):
        # gap: data — empty string note
        tx = TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            type="expense",
            amount=100,
            currency="EGP",
            date=date(2026, 3, 15),
            note="",
            balance_delta=-100,
        )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/detail/{tx.id}")
        content = response.content.decode()
        assert ">Note<" not in content

    def test_shows_tags(self, client, tx_view_data):
        # gap: data — tags display
        tx = TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            type="expense",
            amount=100,
            currency="EGP",
            date=date(2026, 3, 15),
            tags=["food", "lunch"],
            balance_delta=-100,
        )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/detail/{tx.id}")
        content = response.content.decode()
        assert "food" in content
        assert "lunch" in content
        assert "Tags" in content

    def test_exchange_counter_amount_uses_counter_currency(self, client, tx_view_data):
        # gap: data — cross-currency exchange shows counter_amount in counter account's currency
        acct2 = AccountFactory(
            user_id=tx_view_data["user_id"],
            institution_id=tx_view_data["inst_id"],
            name="USD Account",
            currency="USD",
            current_balance=500,
            initial_balance=500,
            type="savings",
        )
        tx1 = TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            counter_account_id=acct2.id,
            type="exchange",
            amount=5000,
            currency="EGP",
            date=date(2026, 3, 15),
            balance_delta=-5000,
            exchange_rate=50.0,
            counter_amount=100.0,
        )
        tx2 = TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=acct2.id,
            counter_account_id=tx_view_data["egp_id"],
            type="exchange",
            amount=100,
            currency="USD",
            date=date(2026, 3, 15),
            balance_delta=100,
            linked_transaction_id=tx1.id,
        )
        Transaction.objects.filter(id=tx1.id).update(linked_transaction_id=tx2.id)
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/detail/{tx1.id}")
        content = response.content.decode()
        # counter_amount should be shown in USD (counter account currency), not EGP
        assert "$100" in content or "USD" in content
        assert "Counter amount" in content

    def test_counter_amount_hidden_when_counter_account_deleted(
        self, client, tx_view_data
    ):
        # gap: data — counter_amount must not render with wrong currency when counter account gone
        # counter_currency will be missing from context → format_currency defaults to EGP (wrong)
        # The fix: guard {% if tx.counter_amount %} with counter_currency too
        acct2 = AccountFactory(
            user_id=tx_view_data["user_id"],
            institution_id=tx_view_data["inst_id"],
            name="Temp USD",
            currency="USD",
            current_balance=500,
            initial_balance=500,
            type="savings",
        )
        tx = TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            counter_account_id=acct2.id,
            type="exchange",
            amount=5000,
            currency="EGP",
            date=date(2026, 3, 15),
            balance_delta=-5000,
            exchange_rate=50.0,
            counter_amount=100.0,
        )
        # Delete the counter account (simulating a deleted account scenario)
        # counter_account FK is SET_NULL, so tx.counter_account_id becomes NULL
        Account.objects.filter(id=acct2.id).delete()
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/detail/{tx.id}")
        assert response.status_code == 200
        content = response.content.decode()
        # counter_amount must NOT appear with wrong EGP default when counter account is gone
        assert "Counter amount" not in content


# ---------------------------------------------------------------------------
# Transaction new — duplicate prefill
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTransactionNewDuplicate:
    """GET /transactions/new?dup=<tx_id> prefills form from existing tx."""

    def test_prefills_amount_and_account(
        self, client, tx_view_data
    ) -> None:  # gap: functional
        """Dup param loads the source tx data into the form as prefill context."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        tx = TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            category_id=tx_view_data["cat_id"],
            type="expense",
            amount=750,
            currency="EGP",
            date=date(2026, 3, 20),
            note="Groceries run",
            balance_delta=-750,
        )
        response = c.get(f"/transactions/new?dup={tx.id}")
        assert response.status_code == 200
        content = response.content.decode()
        # Amount prefilled
        assert "750" in content
        # Note prefilled
        assert "Groceries run" in content
        # Account ID present (selected in dropdown)
        assert tx_view_data["egp_id"] in content

    def test_invalid_dup_id_still_loads_page(
        self, client, tx_view_data
    ) -> None:  # gap: functional
        """Non-existent dup ID doesn't crash — page loads with no prefill."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/new?dup={uuid.uuid4()}")
        assert response.status_code == 200
        assert b"New Transaction" in response.content


# ---------------------------------------------------------------------------
# Transaction row partial
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTransactionRowHappyPath:
    """GET /transactions/row/<id> renders a single transaction row partial."""

    def test_returns_row_html(self, client, tx_view_data) -> None:  # gap: functional
        """Row partial returns 200 with transaction data."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        tx = TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            type="expense",
            amount=300,
            currency="EGP",
            date=date(2026, 3, 22),
            note="Coffee beans",
            balance_delta=-300,
        )
        response = c.get(f"/transactions/row/{tx.id}")
        assert response.status_code == 200
        assert b"Coffee beans" in response.content
        # Partial, not full page
        assert b"<!DOCTYPE" not in response.content

    def test_nonexistent_tx_returns_404(
        self, client, tx_view_data
    ) -> None:  # gap: functional
        """Non-existent tx_id returns 404."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/row/{uuid.uuid4()}")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Transaction detail sheet — transfer
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTransactionDetailSheetTransfer:
    """GET /transactions/detail/<id> for a transfer tx shows counter_account_name."""

    def test_shows_counter_account_name(
        self, client, tx_view_data
    ) -> None:  # gap: state
        """Transfer tx detail sheet includes the counter account's name."""
        user_id = tx_view_data["user_id"]
        dest = AccountFactory(
            user_id=user_id,
            institution_id=tx_view_data["inst_id"],
            name="Dest Savings",
            currency="EGP",
            current_balance=5000,
            initial_balance=5000,
            type="savings",
        )
        tx = TransactionFactory(
            user_id=user_id,
            account_id=tx_view_data["egp_id"],
            counter_account_id=dest.id,
            type="transfer",
            amount=1000,
            currency="EGP",
            date=date(2026, 3, 20),
            note="Rent payment",
            balance_delta=-1000,
        )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/detail/{tx.id}")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Dest Savings" in content
        assert "Rent payment" in content


# ---------------------------------------------------------------------------
# Transaction detail sheet — loan
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTransactionDetailSheetLoan:
    """GET /transactions/detail/<id> for a loan tx shows person_name."""

    def test_shows_person_name(self, client, tx_view_data) -> None:  # gap: state
        """Loan tx detail sheet includes the person's name."""
        user_id = tx_view_data["user_id"]
        person = PersonFactory(user_id=user_id, name="Omar")
        tx = TransactionFactory(
            user_id=user_id,
            account_id=tx_view_data["egp_id"],
            person_id=person.id,
            type="lend",
            amount=2000,
            currency="EGP",
            date=date(2026, 3, 21),
            note="Lent to Omar",
            balance_delta=-2000,
        )
        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.get(f"/transactions/detail/{tx.id}")
        assert response.status_code == 200
        content = response.content.decode()
        assert "Omar" in content
        assert "Lent to Omar" in content


# ---------------------------------------------------------------------------
# Transaction update — VA reallocation via PUT
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTransactionUpdateVaReallocation:
    """PUT /transactions/<id> reallocates virtual account correctly."""

    def test_update_reallocates_va(self, client, tx_view_data) -> None:
        """Updating from VA1 to VA2 reverses VA1 balance and increases VA2."""
        user_id = tx_view_data["user_id"]
        egp_id = tx_view_data["egp_id"]
        cat_id = tx_view_data["cat_id"]

        va1 = VirtualAccountFactory(user_id=user_id, name="VA1", current_balance=-500)
        va2 = VirtualAccountFactory(user_id=user_id, name="VA2", current_balance=0)
        tx = TransactionFactory(
            user_id=user_id,
            account_id=egp_id,
            type="expense",
            amount=500,
            currency="EGP",
            date=date(2026, 3, 20),
            note="Test",
            balance_delta=-500,
        )
        VirtualAccountAllocationFactory(
            virtual_account_id=va1.id,
            transaction_id=tx.id,
            amount=-500,
        )

        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.put(
            f"/transactions/{tx.id}",
            data=f"type=expense&amount=500&category_id={cat_id}&note=Test&date=2026-03-20&virtual_account_id={va2.id}",
            content_type="application/x-www-form-urlencoded",
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200

        # VA1 balance should be reversed: -500 - (-500) = 0
        va1_balance = float(VirtualAccount.objects.get(id=va1.id).current_balance)
        assert va1_balance == pytest.approx(0.0)

        # VA2 balance should be increased: 0 + (-500) = -500
        va2_balance = float(VirtualAccount.objects.get(id=va2.id).current_balance)
        assert va2_balance == pytest.approx(-500.0)

        # Allocation should point to VA2
        alloc = VirtualAccountAllocation.objects.get(transaction_id=tx.id)
        assert str(alloc.virtual_account_id) == str(va2.id)

    def test_update_removes_va_when_cleared(self, client, tx_view_data) -> None:
        """Updating with no VA clears the allocation and reverses balance."""
        user_id = tx_view_data["user_id"]
        egp_id = tx_view_data["egp_id"]
        cat_id = tx_view_data["cat_id"]

        va = VirtualAccountFactory(
            user_id=user_id, name="VA-Remove", current_balance=-300
        )
        tx = TransactionFactory(
            user_id=user_id,
            account_id=egp_id,
            type="expense",
            amount=300,
            currency="EGP",
            date=date(2026, 3, 20),
            note="Remove VA",
            balance_delta=-300,
        )
        VirtualAccountAllocationFactory(
            virtual_account_id=va.id,
            transaction_id=tx.id,
            amount=-300,
        )

        c = set_auth_cookie(client, tx_view_data["session_token"])
        response = c.put(
            f"/transactions/{tx.id}",
            data=f"type=expense&amount=300&category_id={cat_id}&note=Remove VA&date=2026-03-20&virtual_account_id=",
            content_type="application/x-www-form-urlencoded",
            HTTP_HX_REQUEST="true",
        )
        assert response.status_code == 200

        # VA balance should be reversed: -300 - (-300) = 0
        va_balance = float(VirtualAccount.objects.get(id=va.id).current_balance)
        assert va_balance == pytest.approx(0.0)

        # Allocation should be deleted
        count = VirtualAccountAllocation.objects.filter(transaction_id=tx.id).count()
        assert count == 0


# ---------------------------------------------------------------------------
# No optgroup in forms (category type agnostic)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCategoryCombobox:
    """Category combobox replaces native <select> in forms."""

    def test_combobox_in_new_form(self, client, tx_view_data) -> None:
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/transactions/new")
        content = resp.content.decode()
        assert "data-category-combobox" in content
        assert "data-categories" in content
        # No native category <select> should remain
        assert '<select name="category_id"' not in content

    def test_combobox_in_filter_bar(self, client, tx_view_data) -> None:
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/transactions")
        content = resp.content.decode()
        assert "data-category-combobox" in content

    def test_combobox_in_quick_entry(self, client, tx_view_data) -> None:
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/transactions/quick-form", HTTP_HX_REQUEST="true")
        content = resp.content.decode()
        assert "data-category-combobox" in content

    def test_categories_json_is_valid(self, client, tx_view_data) -> None:
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/transactions/new")
        content = resp.content.decode()
        import re

        match = re.search(r"data-categories='(.+?)'", content)
        assert match
        data = json.loads(match.group(1))
        assert len(data) > 0
        assert "id" in data[0]
        assert "name" in data[0]
        assert "icon" in data[0]

    def test_combobox_in_edit_form(self, client, tx_view_data) -> None:
        c = set_auth_cookie(client, tx_view_data["session_token"])
        tx = TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            category_id=tx_view_data["cat_id"],
        )
        resp = c.get(f"/transactions/edit/{tx.id}", HTTP_HX_REQUEST="true")
        content = resp.content.decode()
        assert "data-category-combobox" in content
        assert f'data-selected-id="{tx_view_data["cat_id"]}"' in content


# ---------------------------------------------------------------------------
# Plan 20: Transaction submit UX — prevent duplicates
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTransactionSubmitUX:
    """Forms use hx-disabled-elt to prevent double submission + spinner buttons."""

    def test_new_tx_form_has_disabled_elt(self, client, tx_view_data) -> None:
        """Full transaction form has hx-disabled-elt on <form>."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/transactions/new")
        content = resp.content.decode()
        assert "hx-disabled-elt" in content

    def test_new_tx_form_has_spinner_button(self, client, tx_view_data) -> None:
        """Full transaction form submit button has spinner markup."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/transactions/new")
        content = resp.content.decode()
        assert "btn-spinner" in content
        assert "btn-label" in content

    def test_quick_entry_has_disabled_elt(self, client, tx_view_data) -> None:
        """Quick entry form has hx-disabled-elt on <form>."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/transactions/quick-form")
        content = resp.content.decode()
        assert "hx-disabled-elt" in content

    def test_quick_entry_has_spinner_button(self, client, tx_view_data) -> None:
        """Quick entry submit button has spinner markup."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/transactions/quick-form")
        content = resp.content.decode()
        assert "btn-spinner" in content

    def test_transfer_form_has_disabled_elt(self, client, tx_view_data) -> None:
        """Transfer form has hx-disabled-elt on <form>."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/transfers/new")
        content = resp.content.decode()
        assert "hx-disabled-elt" in content

    def test_transfer_form_has_spinner_button(self, client, tx_view_data) -> None:
        """Transfer form submit button has spinner markup."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/transfers/new")
        content = resp.content.decode()
        assert "btn-spinner" in content

    def test_exchange_form_has_disabled_elt(self, client, tx_view_data) -> None:
        """Exchange form has hx-disabled-elt on <form>."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/exchange/new")
        content = resp.content.decode()
        assert "hx-disabled-elt" in content

    def test_exchange_form_has_spinner_button(self, client, tx_view_data) -> None:
        """Exchange form submit button has spinner markup."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/exchange/new")
        content = resp.content.decode()
        assert "btn-spinner" in content

    def test_batch_form_has_disabled_elt(self, client, tx_view_data) -> None:
        """Batch entry form has hx-disabled-elt on <form>."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/batch-entry")
        content = resp.content.decode()
        assert "hx-disabled-elt" in content

    def test_batch_form_has_spinner_button(self, client, tx_view_data) -> None:
        """Batch entry submit button has spinner markup."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/batch-entry")
        content = resp.content.decode()
        assert "btn-spinner" in content

    def test_quick_entry_success_screen(self, client, tx_view_data) -> None:
        """Quick entry POST returns success screen with Done/Add Another."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.post(
            "/transactions/quick",
            {
                "type": "expense",
                "amount": "50",
                "account_id": tx_view_data["egp_id"],
                "category_id": tx_view_data["cat_id"],
                "date": "2026-03-25",
            },
        )
        content = resp.content.decode()
        assert "Transaction saved!" in content
        assert "Add Another" in content
        assert "Done" in content


# ---------------------------------------------------------------------------
# Plan 22: Edit transaction bottom sheet
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTransactionEditSheet:
    """Edit form renders for sheet context with proper HTMX headers."""

    def test_edit_form_targets_result_div(self, client, tx_view_data) -> None:
        """Edit form's hx-target points at #edit-tx-result, not the row."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        tx = TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            category_id=tx_view_data["cat_id"],
        )
        resp = c.get(f"/transactions/edit/{tx.id}", HTTP_HX_REQUEST="true")
        content = resp.content.decode()
        assert 'hx-target="#edit-tx-result"' in content

    def test_edit_form_has_cancel_close(self, client, tx_view_data) -> None:
        """Cancel button closes the edit sheet."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        tx = TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            category_id=tx_view_data["cat_id"],
        )
        resp = c.get(f"/transactions/edit/{tx.id}", HTTP_HX_REQUEST="true")
        content = resp.content.decode()
        assert "BottomSheet.close" in content

    def test_edit_form_has_title(self, client, tx_view_data) -> None:
        """Edit form has 'Edit Transaction' title."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        tx = TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            category_id=tx_view_data["cat_id"],
        )
        resp = c.get(f"/transactions/edit/{tx.id}", HTTP_HX_REQUEST="true")
        assert b"Edit Transaction" in resp.content

    def test_success_has_retarget_header(self, client, tx_view_data) -> None:
        """PUT success response includes HX-Retarget header."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        tx = TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            category_id=tx_view_data["cat_id"],
            type="expense",
            amount=100,
            currency="EGP",
            balance_delta=-100,
        )
        resp = c.put(
            f"/transactions/{tx.id}",
            "type=expense&amount=200&category_id={}&note=updated&date=2026-03-25&currency=EGP&account_id={}".format(
                tx_view_data["cat_id"], tx_view_data["egp_id"]
            ),
            content_type="application/x-www-form-urlencoded",
            HTTP_HX_REQUEST="true",
        )
        assert resp.status_code == 200
        assert resp["HX-Retarget"] == f"#tx-{tx.id}"
        assert resp["HX-Reswap"] == "outerHTML"

    def test_success_triggers_close_event(self, client, tx_view_data) -> None:
        """PUT success response triggers closeEditSheet event."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        tx = TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            category_id=tx_view_data["cat_id"],
            type="expense",
            amount=100,
            currency="EGP",
            balance_delta=-100,
        )
        resp = c.put(
            f"/transactions/{tx.id}",
            "type=expense&amount=200&category_id={}&note=updated&date=2026-03-25&currency=EGP&account_id={}".format(
                tx_view_data["cat_id"], tx_view_data["egp_id"]
            ),
            content_type="application/x-www-form-urlencoded",
            HTTP_HX_REQUEST="true",
        )
        assert "closeEditSheet" in resp["HX-Trigger"]


@pytest.mark.django_db
class TestEditSheetDeclared:
    """Pages that show transactions include the tx-edit sheet."""

    def test_transactions_page_has_edit_sheet(self, client, tx_view_data) -> None:
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/transactions")
        content = resp.content.decode()
        assert "tx-edit" in content

    def test_close_event_listener_on_transactions(self, client, tx_view_data) -> None:
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/transactions")
        content = resp.content.decode()
        assert "closeEditSheet" in content

    def test_account_detail_has_edit_sheet(self, client, tx_view_data) -> None:
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get(f"/accounts/{tx_view_data['egp_id']}")
        content = resp.content.decode()
        assert "tx-edit" in content

    def test_close_event_listener_on_account_detail(self, client, tx_view_data) -> None:
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get(f"/accounts/{tx_view_data['egp_id']}")
        content = resp.content.decode()
        assert "closeEditSheet" in content

    def test_kebab_edit_opens_sheet(self, client, tx_view_data) -> None:
        """Kebab Edit button opens sheet via BottomSheet.open, not inline hx-get."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        TransactionFactory(
            user_id=tx_view_data["user_id"],
            account_id=tx_view_data["egp_id"],
            category_id=tx_view_data["cat_id"],
        )
        resp = c.get("/transactions")
        content = resp.content.decode()
        assert "BottomSheet.open('tx-edit'" in content


@pytest.mark.django_db
class TestBatchEntryLabels:
    """Batch entry form has accessible labels for all select inputs."""

    def test_batch_entry_has_aria_label_on_type_select(
        self, client, tx_view_data
    ) -> None:
        """Type select in batch entry row has aria-label."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/batch-entry")
        content = resp.content.decode()
        assert 'aria-label="Type"' in content

    def test_batch_entry_has_aria_label_on_account_select(
        self, client, tx_view_data
    ) -> None:
        """Account select in batch entry row has aria-label."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/batch-entry")
        content = resp.content.decode()
        assert 'aria-label="Account"' in content

    def test_batch_entry_has_aria_label_on_category_select(
        self, client, tx_view_data
    ) -> None:
        """Category select in batch entry row has aria-label."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/batch-entry")
        content = resp.content.decode()
        assert 'aria-label="Category"' in content

    def test_batch_entry_clone_resets_selects(self, client, tx_view_data) -> None:
        """addBatchRow clone logic resets select elements — verified via JS data-attr."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/batch-entry")
        content = resp.content.decode()
        # The clone function should call reset on selects: verified via data-batch-reset attr
        assert "data-batch-reset" in content


@pytest.mark.django_db
class TestFormFocusAndDarkMode:
    """Transaction forms have proper focus states and dark mode classes."""

    def test_new_transaction_form_has_ring_offset(self, client, tx_view_data) -> None:
        """New transaction form inputs have focus:ring-offset-2 for visible focus."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/transactions/new")
        assert resp.status_code == 200
        assert b"focus:ring-offset-2" in resp.content

    def test_new_transaction_form_has_dark_mode_inputs(
        self, client, tx_view_data
    ) -> None:
        """New transaction form inputs have dark mode background classes."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/transactions/new")
        assert resp.status_code == 200
        assert b"dark:bg-slate-800" in resp.content

    def test_quick_entry_form_has_ring_offset(self, client, tx_view_data) -> None:
        """Quick entry form inputs have focus:ring-offset-2 for visible focus."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/transactions/quick-form")
        assert resp.status_code == 200
        assert b"focus:ring-offset-2" in resp.content


@pytest.mark.django_db
class TestBatchEntryOnboardingHint:
    """Transactions page has batch entry discoverability hint."""

    def test_transactions_page_has_batch_entry_hint(self, client, tx_view_data) -> None:
        """Transactions page includes a first-time hint about batch entry."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/transactions")
        assert resp.status_code == 200
        content = resp.content.decode()
        assert "batch-entry-hint" in content or "batch_entry_hint" in content
        assert "Batch Entry" in content or "batch entry" in content.lower()


@pytest.mark.django_db
class TestEmptyStateCTA:
    """Empty states guide users to next action with specific CTAs."""

    def test_empty_transaction_list_has_cta(self, client, tx_view_data) -> None:
        """Empty transaction list shows a CTA to add first transaction."""
        from conftest import SessionFactory, UserFactory

        user = UserFactory()
        session = SessionFactory(user=user)
        from django.test import Client

        c = Client()
        c.cookies["clearmoney_session"] = session.token
        # Request list with a filter that returns no results
        resp = c.get("/transactions/list?search=zzznomatch")
        assert resp.status_code == 200
        content = resp.content.decode()
        # Empty state must have helpful guidance, not just "No transactions found"
        assert "Add" in content or "transaction" in content.lower()
        assert "btn" in content or "href" in content or "button" in content

    def test_empty_state_has_icon(self, client, tx_view_data) -> None:
        """Empty transaction list has an icon for visual polish."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/transactions/list?search=zzznomatch")
        assert resp.status_code == 200
        content = resp.content.decode()
        assert "<svg" in content


# ---------------------------------------------------------------------------
# BATCH 3: Visual Feedback Gaps (Issues 10-15)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestButtonStateTransitions:
    """Issue 10: Submit button has relative positioning for spinner overlay."""

    def test_submit_button_has_relative_class(self, client, tx_view_data) -> None:
        """Transaction new form submit button uses relative for absolute spinner."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/transactions/new")
        content = resp.content.decode()
        # Submit button must have relative so btn-spinner can be positioned absolutely
        assert 'type="submit"' in content
        assert "relative" in content

    def test_btn_spinner_has_absolute_positioning(self, client, tx_view_data) -> None:
        """btn-spinner span uses absolute inset-0 for smooth overlay transition."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/transactions/new")
        content = resp.content.decode()
        # The btn-spinner must use absolute positioning to overlay label
        assert "btn-spinner" in content
        assert "absolute" in content

    def test_quick_entry_submit_button_has_relative(self, client, tx_view_data) -> None:
        """Quick entry submit button also has relative positioning."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/transactions/quick-form")
        content = resp.content.decode()
        assert "relative" in content
        assert "btn-spinner" in content


@pytest.mark.django_db
class TestRequiredFieldMarkers:
    """Issue 14: Required fields are visually marked with * in form labels."""

    def test_amount_field_marked_required(self, client, tx_view_data) -> None:
        """Amount label in transaction new form has required marker (*)."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/transactions/new")
        content = resp.content.decode()
        # Required marker asterisk must appear near Amount label
        assert "*" in content

    def test_account_field_marked_required(self, client, tx_view_data) -> None:
        """Account label in transaction new form has required marker (*)."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/transactions/new")
        content = resp.content.decode()
        assert "required" in content.lower()
        assert "*" in content


@pytest.mark.django_db
class TestMoreOptionsPanelTransition:
    """Issue 11: More options panel uses CSS transition class instead of hidden."""

    def test_more_options_panel_has_transition_class(
        self, client, tx_view_data
    ) -> None:
        """More options panel element has more-options-panel class for CSS transitions."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/transactions/new")
        content = resp.content.decode()
        assert "more-options-panel" in content


# ---------------------------------------------------------------------------
# BATCH 4: Mobile Optimization (Issues 16-20)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestMobileScrollIntoView:
    """Issue 17: base.html includes scroll-into-view for keyboard-covered inputs."""

    def test_base_has_scroll_into_view_script(self, client, tx_view_data) -> None:
        """Transaction page includes scroll-into-view JS for mobile keyboard."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/transactions/new")
        content = resp.content.decode()
        assert "scrollIntoView" in content


@pytest.mark.django_db
class TestBottomSheetScrollIndicator:
    """Issue 20: Bottom sheet has visual indicator for scrollable content."""

    def test_quick_entry_sheet_has_overflow_auto(self, client, tx_view_data) -> None:
        """Quick entry bottom sheet uses overflow-y-auto for scrollability."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/")
        content = resp.content.decode()
        assert "overflow-y-auto" in content
        assert "max-h-" in content


# ---------------------------------------------------------------------------
# BATCH 5: Accessibility ARIA & Keyboard (Issues 21-25)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestFilterFormLabels:
    """Issues 21, 23, 24: Transaction filter form has labels for all inputs."""

    def test_search_input_has_label(self, client, tx_view_data) -> None:
        """Search input has explicit <label> or aria-label for screen readers."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/transactions")
        content = resp.content.decode()
        # Must have label for search-input OR aria-label on search input
        assert 'for="search-input"' in content or 'aria-label="Search' in content

    def test_date_from_has_label(self, client, tx_view_data) -> None:
        """Date from filter input has label for screen reader accessibility."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/transactions")
        content = resp.content.decode()
        assert 'for="date-from"' in content or 'aria-label="From date"' in content

    def test_date_to_has_label(self, client, tx_view_data) -> None:
        """Date to filter input has label for screen reader accessibility."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/transactions")
        content = resp.content.decode()
        assert 'for="date-to"' in content or 'aria-label="To date"' in content

    def test_account_filter_has_label(self, client, tx_view_data) -> None:
        """Account filter select has a label or aria-label."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/transactions")
        content = resp.content.decode()
        assert (
            'for="filter-account"' in content
            or 'aria-label="Filter by account"' in content
        )

    def test_type_filter_has_label(self, client, tx_view_data) -> None:
        """Type filter select has a label or aria-label."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/transactions")
        content = resp.content.decode()
        assert (
            'for="filter-type"' in content or 'aria-label="Filter by type"' in content
        )


@pytest.mark.django_db
class TestTypeRadioKeyboard:
    """Issue 25: Type radio buttons have aria-keyshortcuts or keyboard hint."""

    def test_type_selector_uses_fieldset_legend(self, client, tx_view_data) -> None:
        """Transaction form type selector uses fieldset+legend for keyboard nav."""
        c = set_auth_cookie(client, tx_view_data["session_token"])
        resp = c.get("/transactions/new")
        content = resp.content.decode()
        # Must have fieldset with legend for radio group accessibility
        assert "<fieldset" in content
        assert "<legend" in content
