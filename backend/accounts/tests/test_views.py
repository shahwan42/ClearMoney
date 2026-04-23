"""
Accounts view tests — HTTP-level tests for all /accounts/* and /institutions/* routes.

Fixtures create test data via factory_boy factories, tests hit endpoints via Django test client.
"""

import uuid
from datetime import date

import pytest

from accounts.models import Account, Institution
from conftest import SessionFactory, UserFactory, set_auth_cookie
from tests.factories import (
    AccountFactory,
    CategoryFactory,
    CurrencyFactory,
    InstitutionFactory,
    TransactionFactory,
    VirtualAccountFactory,
)
from transactions.models import Transaction


@pytest.fixture
def accounts_data(db):
    """User + session + institution + 2 accounts (savings + CC) + transaction.

    Creates minimal data for accounts views. Yields dict with IDs.
    """
    user = UserFactory()
    session = SessionFactory(user=user)

    inst = InstitutionFactory(user_id=user.id, name="Test Bank", type="bank")
    savings = AccountFactory(
        user_id=user.id,
        institution_id=inst.id,
        name="Main Savings",
        type="savings",
        currency="EGP",
        current_balance=15000,
        initial_balance=15000,
    )
    cc = AccountFactory(
        user_id=user.id,
        institution_id=inst.id,
        name="Test CC",
        type="credit_card",
        currency="EGP",
        current_balance=-5000,
        initial_balance=0,
        credit_limit=50000,
        metadata={"statement_day": 15, "due_day": 5},
    )
    TransactionFactory(
        user_id=user.id,
        account_id=savings.id,
        type="expense",
        amount=500,
        currency="EGP",
        date=date(2026, 3, 15),
        note="Test tx",
        balance_delta=-500,
    )

    yield {
        "user_id": str(user.id),
        "session_token": session.token,
        "institution_id": str(inst.id),
        "savings_id": str(savings.id),
        "cc_id": str(cc.id),
    }


@pytest.fixture
def empty_user(db):
    """User + session with no data (for empty state tests)."""
    user = UserFactory()
    session = SessionFactory(user=user)

    yield {"user_id": str(user.id), "session_token": session.token}


# ---------------------------------------------------------------------------
# Accounts list page
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAccountsList:
    def test_200(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.get("/accounts")
        assert response.status_code == 200
        assert b"Accounts" in response.content

    def test_shows_institution_and_accounts(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.get("/accounts")
        assert b"Test Bank" in response.content
        assert b"Main Savings" in response.content
        assert b"Test CC" in response.content

    def test_empty_state(self, client, empty_user):
        c = set_auth_cookie(client, empty_user["session_token"])
        response = c.get("/accounts")
        assert response.status_code == 200
        assert b"No accounts yet" in response.content

    def test_redirects_without_auth(self, client):
        response = client.get("/accounts")
        assert response.status_code == 302
        assert "/login" in response.url

    def test_header_shows_selected_currency_selector(self, client, accounts_data):
        CurrencyFactory(code="EGP", name="Egyptian Pound", display_order=0)
        CurrencyFactory(code="EUR", name="Euro", display_order=1)
        from auth_app.currency import (
            set_user_active_currencies,
            set_user_selected_display_currency,
        )

        set_user_active_currencies(accounts_data["user_id"], ["EGP", "EUR"])
        set_user_selected_display_currency(accounts_data["user_id"], "EUR")

        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.get("/accounts")
        assert response.status_code == 200
        assert b"header-display-currency" in response.content
        assert b'value="EUR" selected' in response.content


# ---------------------------------------------------------------------------
# Account detail page
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAccountDetail:
    def test_200(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.get(f"/accounts/{accounts_data['savings_id']}")
        assert response.status_code == 200
        assert b"Main Savings" in response.content

    def test_shows_balance(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.get(f"/accounts/{accounts_data['savings_id']}")
        assert b"15,000" in response.content

    def test_shows_transactions(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.get(f"/accounts/{accounts_data['savings_id']}")
        assert b"Test tx" in response.content

    def test_404_nonexistent(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.get(f"/accounts/{uuid.uuid4()}")
        assert response.status_code == 404

    def test_cc_shows_utilization(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.get(f"/accounts/{accounts_data['cc_id']}")
        assert response.status_code == 200
        assert b"Credit Utilization" in response.content

    def test_transaction_row_shows_category(self, client, accounts_data):
        """Account detail transaction rows display category icon and name."""
        user_id = accounts_data["user_id"]
        cat = CategoryFactory(
            user_id=user_id, name={"en": "Groceries"}, type="expense", icon="🍕"
        )
        Transaction.objects.filter(user_id=user_id).update(category_id=cat.id)
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.get(f"/accounts/{accounts_data['savings_id']}")
        content = response.content.decode()
        assert "🍕" in content
        assert "Groceries" in content

    def test_transaction_row_hides_account_name(self, client, accounts_data):
        """Account detail transaction rows do not repeat the account name (hide_account_name=True)."""
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.get(f"/accounts/{accounts_data['savings_id']}")
        content = response.content.decode()
        # The account name appears in the page header but must not appear inside a row's
        # secondary info line — check the row secondary span specifically
        assert "· Main Savings" not in content

    def test_shows_balance_check_cta(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.get(f"/accounts/{accounts_data['savings_id']}")
        assert b"Balance Check" in response.content

    def test_linked_virtual_accounts_use_account_currency(self, client, accounts_data):
        usd_account = AccountFactory(
            user_id=accounts_data["user_id"],
            institution_id=accounts_data["institution_id"],
            name="USD Savings",
            type="savings",
            currency="USD",
            current_balance=1000,
            initial_balance=1000,
        )
        VirtualAccountFactory(
            user_id=accounts_data["user_id"],
            account=usd_account,
            name="USD Goal",
            current_balance=150,
            target_amount=250,
        )
        c = set_auth_cookie(client, accounts_data["session_token"])

        response = c.get(f"/accounts/{usd_account.id}")

        assert response.status_code == 200
        assert b"USD Goal" in response.content
        assert b"$150.00" in response.content
        assert b"EGP 150.00" not in response.content


@pytest.mark.django_db
class TestBalanceCheckPage:
    def test_200(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.get(f"/accounts/{accounts_data['savings_id']}/balance-check")
        assert response.status_code == 200
        assert b"Balance Check" in response.content

    def test_submit_mismatch_shows_correction(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.post(
            f"/accounts/{accounts_data['savings_id']}/balance-check/submit",
            {"bank_balance": "14000"},
        )
        assert response.status_code == 200
        assert b"Create Balance Correction" in response.content

    def test_submit_match_redirects_to_detail(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.post(
            f"/accounts/{accounts_data['savings_id']}/balance-check/submit",
            {"bank_balance": "15000"},
        )
        assert response.status_code == 302
        assert (
            response.headers["Location"] == f"/accounts/{accounts_data['savings_id']}"
        )


# ---------------------------------------------------------------------------
# HTMX partials
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAccountFormPartial:
    def test_200(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.get(
            f"/accounts/form?institution_id={accounts_data['institution_id']}"
        )
        assert response.status_code == 200
        assert b"Add Account" in response.content

    def test_missing_institution_id(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.get("/accounts/form")
        assert response.status_code == 400


@pytest.mark.django_db
class TestInstitutionFormPartial:
    def test_200(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.get("/accounts/institution-form")
        assert response.status_code == 200
        assert b"Add Institution" in response.content


# ---------------------------------------------------------------------------
# Institution CRUD
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestInstitutionAdd:
    def test_creates_institution(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.post("/institutions/add", {"name": "New Bank", "type": "bank"})
        assert response.status_code == 200
        assert b"Institution added!" in response.content
        # Verify OOB swap contains the new institution
        assert b"New Bank" in response.content

    def test_rejects_empty_name(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.post("/institutions/add", {"name": "", "type": "bank"})
        assert response.status_code == 422
        # Error message must have role="alert" for screen readers
        assert b'role="alert"' in response.content

    def test_rejects_empty_name_error_has_dark_mode(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.post("/institutions/add", {"name": "", "type": "bank"})
        assert response.status_code == 422
        assert b"dark:" in response.content


@pytest.mark.django_db
class TestInstitutionUpdate:
    def test_updates(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.put(
            f"/institutions/{accounts_data['institution_id']}/update",
            "name=Renamed+Bank&type=bank",
            content_type="application/x-www-form-urlencoded",
        )
        assert response.status_code == 200
        # Response contains the close script + OOB card swap
        assert b"closeEditSheet" in response.content

    def test_rejects_empty_name_error_has_role_alert(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.put(
            f"/institutions/{accounts_data['institution_id']}/update",
            "name=&type=bank",
            content_type="application/x-www-form-urlencoded",
        )
        assert response.status_code == 422
        assert b'role="alert"' in response.content
        assert b"dark:" in response.content


@pytest.mark.django_db
class TestInstitutionDelete:
    def test_cascades(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.delete(f"/institutions/{accounts_data['institution_id']}/delete")
        assert response.status_code == 200
        assert b"Institution deleted!" in response.content

        # Verify accounts were cascade-deleted
        assert (
            Account.objects.filter(
                institution_id=accounts_data["institution_id"]
            ).count()
            == 0
        )


@pytest.mark.django_db
class TestInstitutionDeleteConfirm:
    def test_200(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.get(
            f"/institutions/{accounts_data['institution_id']}/delete-confirm"
        )
        assert response.status_code == 200
        assert b"Delete Institution" in response.content
        assert b"Test Bank" in response.content


# ---------------------------------------------------------------------------
# Account CRUD
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAccountAdd:
    def test_creates_account(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.post(
            "/accounts/add",
            {
                "institution_id": accounts_data["institution_id"],
                "name": "New Savings",
                "type": "savings",
                "currency": "EGP",
                "initial_balance": "5000",
            },
        )
        assert response.status_code == 200
        # Verify OOB swap contains the new account
        assert b"New Savings" in response.content

    def test_cc_requires_credit_limit(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.post(
            "/accounts/add",
            {
                "institution_id": accounts_data["institution_id"],
                "name": "My CC",
                "type": "credit_card",
                "currency": "EGP",
            },
        )
        assert response.status_code == 422
        assert b"credit_limit is required" in response.content

    def test_error_has_role_alert(self, client, accounts_data):
        """Account form error must include role=alert and dark mode classes."""
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.post(
            "/accounts/add",
            {
                "institution_id": accounts_data["institution_id"],
                "name": "My CC",
                "type": "credit_card",
                "currency": "EGP",
                # missing credit_limit — triggers error
            },
        )
        assert response.status_code == 422
        assert b'role="alert"' in response.content
        assert b"dark:" in response.content


@pytest.mark.django_db
class TestAccountUpdate:
    def test_updates(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.post(
            f"/accounts/{accounts_data['savings_id']}/edit",
            {"name": "Renamed Savings", "type": "savings", "currency": "EGP"},
        )
        # Without HX-Request header, htmx_redirect returns 302
        assert response.status_code == 302


@pytest.mark.django_db
class TestAccountDelete:
    def test_success(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.delete(f"/accounts/{accounts_data['savings_id']}/delete")
        assert response.status_code == 302


@pytest.mark.django_db
class TestToggleDormant:
    def test_toggles(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.post(f"/accounts/{accounts_data['savings_id']}/dormant")
        assert response.status_code == 302

        # Verify the flag was toggled
        assert Account.objects.get(id=accounts_data["savings_id"]).is_dormant is True


@pytest.mark.django_db
class TestHealthUpdate:
    def test_saves_config(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.post(
            f"/accounts/{accounts_data['savings_id']}/health",
            {"min_balance": "5000", "min_monthly_deposit": "1000"},
        )
        assert response.status_code == 302

        # Verify the config was saved
        config = Account.objects.get(id=accounts_data["savings_id"]).health_config
        assert "5000" in str(config)


@pytest.mark.django_db
class TestReorder:
    def test_reorder_accounts(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.post(
            "/accounts/reorder",
            {
                "id[]": [accounts_data["cc_id"], accounts_data["savings_id"]],
            },
        )
        assert response.status_code == 302

    def test_reorder_institutions(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.post(
            "/institutions/reorder",
            {
                "id[]": [accounts_data["institution_id"]],
            },
        )
        assert response.status_code == 302


# ---------------------------------------------------------------------------
# Credit card statement
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCreditCardStatement:
    def test_200(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.get(f"/accounts/{accounts_data['cc_id']}/statement")
        assert response.status_code == 200
        assert b"Credit Card Statement" in response.content

    def test_non_credit_returns_400(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.get(f"/accounts/{accounts_data['savings_id']}/statement")
        assert response.status_code == 400

    def test_404_nonexistent(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.get(f"/accounts/{uuid.uuid4()}/statement")
        assert response.status_code == 404

    def test_shows_transaction_in_billing_period(self, client, accounts_data):
        """Transaction dated within the billing period appears in the statement."""  # gap: functional
        # statement_day=15, period=2026-03 covers 2026-02-16 to 2026-03-15
        TransactionFactory(
            user_id=accounts_data["user_id"],
            account_id=accounts_data["cc_id"],
            type="expense",
            amount=1234,
            currency="EGP",
            date=date(2026, 3, 10),
            note="CC Charge",
            balance_delta=-1234,
        )
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.get(f"/accounts/{accounts_data['cc_id']}/statement?period=2026-03")
        assert response.status_code == 200
        assert b"CC Charge" in response.content

    def test_excludes_transaction_outside_billing_period(self, client, accounts_data):
        """Transaction outside the requested period is not shown."""  # gap: functional
        TransactionFactory(
            user_id=accounts_data["user_id"],
            account_id=accounts_data["cc_id"],
            type="expense",
            amount=999,
            currency="EGP",
            date=date(2026, 1, 5),
            note="Old Charge",
            balance_delta=-999,
        )
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.get(f"/accounts/{accounts_data['cc_id']}/statement?period=2026-03")
        assert response.status_code == 200
        assert b"Old Charge" not in response.content

    def test_payment_history_shows_transfer_to_cc(self, client, accounts_data):
        """Transfer into the CC account appears in payment history."""  # gap: functional
        TransactionFactory(
            user_id=accounts_data["user_id"],
            account_id=accounts_data["savings_id"],
            counter_account_id=accounts_data["cc_id"],
            type="transfer",
            amount=2000,
            currency="EGP",
            date=date(2026, 3, 10),
            note="CC Payment",
            balance_delta=2000,
        )
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.get(f"/accounts/{accounts_data['cc_id']}/statement?period=2026-03")
        assert response.status_code == 200
        assert b"CC Payment" in response.content


# ---------------------------------------------------------------------------
# Institution preset API
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestInstitutionPresetsView:
    """GET /accounts/institution-presets returns JSON preset lists."""

    def test_returns_bank_presets(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        resp = c.get("/accounts/institution-presets?type=bank")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) > 0
        # All bank entries have required fields
        for entry in data:
            assert "name" in entry
            assert "icon" in entry
            assert "color" in entry

    def test_bank_list_includes_cib(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        resp = c.get("/accounts/institution-presets?type=bank")
        names = [b["name"] for b in resp.json()]
        assert any("CIB" in n for n in names)

    def test_returns_fintech_presets(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        resp = c.get("/accounts/institution-presets?type=fintech")
        assert resp.status_code == 200
        data = resp.json()
        assert any(f["name"] == "Telda" for f in data)

    def test_returns_wallet_presets(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        resp = c.get("/accounts/institution-presets?type=wallet")
        assert resp.status_code == 200
        data = resp.json()
        groups = {w["group"] for w in data}
        assert "physical" in groups
        assert "digital" in groups
        assert any(w["name"] == "Pocket Wallet" for w in data)
        assert any(w["name"] == "Vodafone Cash" for w in data)

    def test_invalid_type_returns_400(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        resp = c.get("/accounts/institution-presets?type=unknown")
        assert resp.status_code == 400

    def test_requires_auth(self, client):
        resp = client.get("/accounts/institution-presets?type=bank")
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# Institution add — icon + color from preset
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestInstitutionCreateWithPreset:
    """POST /institutions/add persists icon and color from preset selection."""

    def test_creates_bank_with_image_icon(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        resp = c.post(
            "/institutions/add",
            {
                "name": "CIB - Commercial International Bank",
                "type": "bank",
                "icon": "cib.svg",
                "color": "#003DA5",
            },
        )
        assert resp.status_code == 200
        inst = Institution.objects.get(
            name="CIB - Commercial International Bank",
            user_id=accounts_data["user_id"],
        )
        assert inst.icon == "cib.svg"
        assert inst.color == "#003DA5"

    def test_creates_wallet_with_emoji_icon(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        resp = c.post(
            "/institutions/add",
            {
                "name": "Pocket Wallet",
                "type": "wallet",
                "icon": "👛",
                "color": "#8B5E3C",
            },
        )
        assert resp.status_code == 200
        inst = Institution.objects.get(
            name="Pocket Wallet",
            user_id=accounts_data["user_id"],
        )
        assert inst.icon == "👛"

    def test_creates_institution_without_icon(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        resp = c.post(
            "/institutions/add",
            {"name": "My Local Bank", "type": "bank"},
        )
        assert resp.status_code == 200
        inst = Institution.objects.get(
            name="My Local Bank",
            user_id=accounts_data["user_id"],
        )
        assert inst.icon is None
        assert inst.color is None


# ---------------------------------------------------------------------------
# Account add — auto-generated name
# ---------------------------------------------------------------------------


class TestAccountAddAutoName:
    """POST /accounts/add with blank name auto-generates a default."""

    def test_blank_name_creates_auto_named_account(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        resp = c.post(
            "/accounts/add",
            {
                "institution_id": accounts_data["institution_id"],
                "name": "",
                "type": "prepaid",
                "currency": "EGP",
                "initial_balance": "0",
            },
        )
        assert resp.status_code == 200
        acct = Account.objects.get(user_id=accounts_data["user_id"], type="prepaid")
        assert acct.name == "Test Bank - Prepaid"

    def test_explicit_name_still_works(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        resp = c.post(
            "/accounts/add",
            {
                "institution_id": accounts_data["institution_id"],
                "name": "My Custom Account",
                "type": "current",
                "currency": "EGP",
                "initial_balance": "1000",
            },
        )
        assert resp.status_code == 200
        assert Account.objects.filter(
            user_id=accounts_data["user_id"], name="My Custom Account"
        ).exists()


# ---------------------------------------------------------------------------
# Institution list partial
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestInstitutionListPartial:
    """GET /accounts/list renders institution list partial."""

    def test_200_with_data(self, client, accounts_data) -> None:  # gap: functional
        """Partial returns institution list HTML with existing data."""
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.get("/accounts/list")
        assert response.status_code == 200
        assert b"Test Bank" in response.content
        assert b"Main Savings" in response.content

    def test_200_empty_user(self, client, empty_user) -> None:  # gap: functional
        """Partial returns 200 even when user has no institutions."""
        c = set_auth_cookie(client, empty_user["session_token"])
        response = c.get("/accounts/list")
        assert response.status_code == 200

    def test_is_partial_not_full_page(
        self, client, accounts_data
    ) -> None:  # gap: functional
        """Response is an HTML fragment, not a full page."""
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.get("/accounts/list")
        assert b"<!DOCTYPE" not in response.content


# ---------------------------------------------------------------------------
# Empty partial
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestEmptyPartial:
    """GET /accounts/empty returns empty HTML for HTMX auto-dismiss."""

    def test_200_empty_body(self, client, accounts_data) -> None:  # gap: functional
        """Returns 200 with empty body."""
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.get("/accounts/empty")
        assert response.status_code == 200
        assert response.content == b""
        assert "text/html" in response["Content-Type"]


# ---------------------------------------------------------------------------
# Account edit form 404
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAccountEditForm404:
    """GET /accounts/<id>/edit-form returns 404 for non-existent account."""

    def test_nonexistent_account_returns_404(
        self, client, accounts_data
    ) -> None:  # gap: functional
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.get(f"/accounts/{uuid.uuid4()}/edit-form")
        assert response.status_code == 404

    def test_valid_account_returns_200(
        self, client, accounts_data
    ) -> None:  # gap: functional
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.get(f"/accounts/{accounts_data['savings_id']}/edit-form")
        assert response.status_code == 200
        assert b"Main Savings" in response.content


# ---------------------------------------------------------------------------
# Institution edit form 404
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestInstitutionEditForm404:
    """GET /institutions/<id>/edit-form returns 404 for non-existent institution."""

    def test_nonexistent_institution_returns_404(
        self, client, accounts_data
    ) -> None:  # gap: functional
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.get(f"/institutions/{uuid.uuid4()}/edit-form")
        assert response.status_code == 404

    def test_valid_institution_returns_200(
        self, client, accounts_data
    ) -> None:  # gap: functional
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.get(f"/institutions/{accounts_data['institution_id']}/edit-form")
        assert response.status_code == 200
        assert b"Test Bank" in response.content


# ---------------------------------------------------------------------------
# Credit card statement — no billing cycle
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestCreditCardStatementNoBillingCycle:
    """GET /accounts/<id>/statement for CC without billing cycle metadata."""

    def test_renders_error_template(self, client, accounts_data) -> None:  # gap: state
        """CC with no billing cycle in metadata renders the error template."""
        cc_no_cycle = AccountFactory(
            user_id=accounts_data["user_id"],
            institution_id=accounts_data["institution_id"],
            name="CC No Cycle",
            type="credit_card",
            currency="EGP",
            current_balance=-2000,
            initial_balance=0,
            credit_limit=30000,
        )
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.get(f"/accounts/{cc_no_cycle.id}/statement")
        assert response.status_code == 200
        assert b"billing cycle" in response.content.lower()

    def test_empty_metadata_renders_error(
        self, client, accounts_data
    ) -> None:  # gap: state
        """CC with empty JSON metadata (no statement_day/due_day) renders error."""
        cc_empty_meta = AccountFactory(
            user_id=accounts_data["user_id"],
            institution_id=accounts_data["institution_id"],
            name="CC Empty Meta",
            type="credit_card",
            currency="EGP",
            current_balance=-1000,
            initial_balance=0,
            credit_limit=20000,
            metadata={},
        )
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.get(f"/accounts/{cc_empty_meta.id}/statement")
        assert response.status_code == 200
        assert b"billing cycle" in response.content.lower()


# ---------------------------------------------------------------------------
# Dark mode hover contrast
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDarkModeHoverClasses:
    """Accounts page has proper dark mode hover states."""

    def test_institution_card_has_dark_hover(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        resp = c.get("/accounts")
        content = resp.content.decode()
        assert "dark:hover:bg-slate-700" in content

    def test_no_bare_hover_bg_gray_50(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        resp = c.get("/accounts")
        content = resp.content.decode()
        for line in content.split("\n"):
            if "hover:bg-gray-50" in line:
                assert "dark:hover:bg-" in line, f"Missing dark hover: {line.strip()}"


# ---------------------------------------------------------------------------
# Plan 21: Unified add account form
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestAccountAddForm:
    """GET /accounts/add-form renders unified form."""

    def test_renders_unified_form(self, client, accounts_data) -> None:
        c = set_auth_cookie(client, accounts_data["session_token"])
        resp = c.get("/accounts/add-form")
        assert resp.status_code == 200
        content = resp.content.decode()
        assert "institution_name" in content or "institution_type" in content
        assert 'name="type"' in content

    def test_preselected_institution(self, client, accounts_data) -> None:
        c = set_auth_cookie(client, accounts_data["session_token"])
        inst_id = accounts_data["institution_id"]
        resp = c.get(f"/accounts/add-form?institution_id={inst_id}")
        content = resp.content.decode()
        assert "Test Bank" in content
        assert f'value="{inst_id}"' in content

    def test_unknown_institution_falls_back(self, client, accounts_data) -> None:
        c = set_auth_cookie(client, accounts_data["session_token"])
        resp = c.get(
            "/accounts/add-form?institution_id=00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code == 200
        content = resp.content.decode()
        assert "institution_type" in content

    def test_requires_auth(self, client) -> None:
        resp = client.get("/accounts/add-form")
        assert resp.status_code == 302

    def test_initial_balance_has_placeholder(self, client, accounts_data) -> None:
        """Initial balance field must have placeholder for user guidance."""
        c = set_auth_cookie(client, accounts_data["session_token"])
        resp = c.get("/accounts/add-form")
        assert resp.status_code == 200
        content = resp.content.decode()
        # The initial_balance input line should include a placeholder attribute
        for line in content.split("\n"):
            if 'name="initial_balance"' in line:
                assert "placeholder" in line, (
                    f"initial_balance input is missing placeholder: {line.strip()}"
                )


@pytest.mark.django_db
class TestAccountAddUnified:
    """POST /accounts/add handles inline institution creation."""

    def test_creates_account_with_inline_institution(
        self, client, accounts_data
    ) -> None:
        c = set_auth_cookie(client, accounts_data["session_token"])
        resp = c.post(
            "/accounts/add",
            {
                "institution_name": "NBE",
                "institution_type": "bank",
                "name": "Savings",
                "type": "savings",
                "currency": "EGP",
                "initial_balance": "1000",
            },
        )
        assert resp.status_code == 200
        assert Institution.objects.filter(
            user_id=accounts_data["user_id"], name="NBE"
        ).exists()
        assert Account.objects.filter(
            user_id=accounts_data["user_id"], name="Savings"
        ).exists()

    def test_reuses_existing_institution(self, client, accounts_data) -> None:
        c = set_auth_cookie(client, accounts_data["session_token"])
        resp = c.post(
            "/accounts/add",
            {
                "institution_name": "Test Bank",
                "institution_type": "bank",
                "name": "Current",
                "type": "current",
                "currency": "EGP",
                "initial_balance": "0",
            },
        )
        assert resp.status_code == 200
        assert (
            Institution.objects.filter(
                user_id=accounts_data["user_id"], name__iexact="Test Bank"
            ).count()
            == 1
        )

    def test_institution_id_still_works(self, client, accounts_data) -> None:
        """Backward compatibility — old flow with institution_id."""
        c = set_auth_cookie(client, accounts_data["session_token"])
        resp = c.post(
            "/accounts/add",
            {
                "institution_id": accounts_data["institution_id"],
                "name": "Current",
                "type": "current",
                "currency": "EGP",
                "initial_balance": "0",
            },
        )
        assert resp.status_code == 200
        assert Account.objects.filter(
            user_id=accounts_data["user_id"], name="Current"
        ).exists()

    def test_missing_institution_name_error(self, client, accounts_data) -> None:
        c = set_auth_cookie(client, accounts_data["session_token"])
        resp = c.post(
            "/accounts/add",
            {
                "name": "Savings",
                "type": "savings",
                "currency": "EGP",
                "initial_balance": "0",
            },
        )
        assert resp.status_code == 422

    def test_old_institution_form_route_still_works(
        self, client, accounts_data
    ) -> None:
        """Production safety — old routes kept."""
        c = set_auth_cookie(client, accounts_data["session_token"])
        resp = c.get("/accounts/institution-form")
        assert resp.status_code == 200

    def test_old_account_form_route_still_works(self, client, accounts_data) -> None:
        """Production safety — old routes kept."""
        c = set_auth_cookie(client, accounts_data["session_token"])
        resp = c.get(f"/accounts/form?institution_id={accounts_data['institution_id']}")
        assert resp.status_code == 200

    def test_accounts_page_shows_plus_account(self, client, accounts_data) -> None:
        """Accounts page button says '+ Account' not '+ Institution'."""
        c = set_auth_cookie(client, accounts_data["session_token"])
        resp = c.get("/accounts")
        content = resp.content.decode()
        assert "+ Account" in content
        assert "+ Institution" not in content

    def test_empty_state_text(self, client, accounts_data) -> None:
        """Empty state text updated."""
        # The accounts_data fixture has accounts so we can't test empty state directly
        # but we can check the template renders correctly
        c = set_auth_cookie(client, accounts_data["session_token"])
        resp = c.get("/accounts")
        assert resp.status_code == 200

    def test_create_sheet_uses_unified_form_url(self, client, accounts_data) -> None:
        """The create sheet JS opens /accounts/add-form (not institution-form)."""
        c = set_auth_cookie(client, accounts_data["session_token"])
        resp = c.get("/accounts")
        content = resp.content.decode()
        assert "/accounts/add-form" in content


@pytest.mark.django_db
class TestDormantToggleARIA:
    """Dormant toggle button has role=switch + aria-checked for accessibility."""

    def test_dormant_toggle_has_role_switch(self, client, accounts_data) -> None:
        """Account detail dormant toggle has role="switch"."""
        c = set_auth_cookie(client, accounts_data["session_token"])
        resp = c.get(f"/accounts/{accounts_data['savings_id']}")
        content = resp.content.decode()
        assert 'role="switch"' in content

    def test_dormant_toggle_aria_checked_false_when_active(
        self, client, accounts_data
    ) -> None:
        """Dormant toggle shows aria-checked=false when account is active."""
        c = set_auth_cookie(client, accounts_data["session_token"])
        resp = c.get(f"/accounts/{accounts_data['savings_id']}")
        content = resp.content.decode()
        assert 'aria-checked="false"' in content

    def test_dormant_toggle_aria_checked_true_when_dormant(
        self, client, accounts_data
    ) -> None:
        """Dormant toggle shows aria-checked=true when account is dormant."""
        Account.objects.filter(id=accounts_data["savings_id"]).update(is_dormant=True)
        c = set_auth_cookie(client, accounts_data["session_token"])
        resp = c.get(f"/accounts/{accounts_data['savings_id']}")
        content = resp.content.decode()
        assert 'aria-checked="true"' in content


@pytest.mark.django_db
class TestCustomAccountNameVisibility:
    """Custom account name field is visible by default (not hidden under toggle)."""

    def test_add_account_form_custom_name_visible(self, client, accounts_data) -> None:
        """The add-account form shows the custom name field without display:none."""
        c = set_auth_cookie(client, accounts_data["session_token"])
        resp = c.get("/accounts/add-form")
        content = resp.content.decode()
        # custom name field should be present without hidden toggle button
        assert 'id="add-acct-custom-name-field"' in content
        # The hidden toggle button should be gone
        assert 'id="add-acct-custom-name-toggle"' not in content


@pytest.mark.django_db
class TestInstitutionButtonTooltips:
    """Institution card buttons have title tooltip attributes for discoverability."""

    def test_edit_button_has_title(self, client, accounts_data) -> None:
        c = set_auth_cookie(client, accounts_data["session_token"])
        resp = c.get("/accounts")
        assert resp.status_code == 200
        content = resp.content.decode()
        # Edit button should have a title tooltip
        assert 'title="Edit institution"' in content or 'title="Edit"' in content

    def test_delete_button_has_title(self, client, accounts_data) -> None:
        c = set_auth_cookie(client, accounts_data["session_token"])
        resp = c.get("/accounts")
        assert resp.status_code == 200
        content = resp.content.decode()
        # Delete button should have a title tooltip
        assert 'title="Delete institution"' in content or 'title="Delete"' in content
