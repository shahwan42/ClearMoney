"""
Accounts view tests — HTTP-level tests for all /accounts/* and /institutions/* routes.

Fixtures create test data via raw SQL, tests hit endpoints via Django test client.
"""

import uuid
from datetime import date

import pytest
from django.db import connection

from conftest import SessionFactory, UserFactory, set_auth_cookie
from core.models import Session, User


@pytest.fixture
def accounts_data(db):
    """User + session + institution + 2 accounts (savings + CC) + transaction.

    Creates minimal data for accounts views. Yields dict with IDs.
    """
    user = UserFactory()
    session = SessionFactory(user=user)
    user_id = str(user.id)
    inst_id = str(uuid.uuid4())
    savings_id = str(uuid.uuid4())
    cc_id = str(uuid.uuid4())

    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO institutions (id, user_id, name, type) VALUES (%s, %s, %s, 'bank')",
            [inst_id, user_id, "Test Bank"],
        )
        cursor.execute(
            "INSERT INTO accounts (id, user_id, institution_id, name, type, currency, current_balance, initial_balance)"
            " VALUES (%s, %s, %s, %s, 'savings', 'EGP', %s, %s)",
            [savings_id, user_id, inst_id, "Main Savings", 15000, 15000],
        )
        cursor.execute(
            "INSERT INTO accounts (id, user_id, institution_id, name, type, currency, current_balance, initial_balance, credit_limit, metadata)"
            " VALUES (%s, %s, %s, %s, 'credit_card', 'EGP', %s, %s, %s, %s::jsonb)",
            [
                cc_id,
                user_id,
                inst_id,
                "Test CC",
                -5000,
                0,
                50000,
                '{"statement_day": 15, "due_day": 5}',
            ],
        )
        # One transaction for the savings account
        cursor.execute(
            "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, note, balance_delta)"
            " VALUES (%s, %s, %s, 'expense', 500, 'EGP', %s, 'Test tx', -500)",
            [str(uuid.uuid4()), user_id, savings_id, date(2026, 3, 15)],
        )

    yield {
        "user_id": user_id,
        "session_token": session.token,
        "institution_id": inst_id,
        "savings_id": savings_id,
        "cc_id": cc_id,
    }

    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM transactions WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM accounts WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM institutions WHERE user_id = %s", [user_id])
    Session.objects.filter(user=user).delete()
    User.objects.filter(id=user.id).delete()


@pytest.fixture
def empty_user(db):
    """User + session with no data (for empty state tests)."""
    user = UserFactory()
    session = SessionFactory(user=user)

    yield {"user_id": str(user.id), "session_token": session.token}

    Session.objects.filter(user=user).delete()
    User.objects.filter(id=user.id).delete()


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
        assert b"No institutions yet" in response.content

    def test_redirects_without_auth(self, client):
        response = client.get("/accounts")
        assert response.status_code == 302
        assert "/login" in response.url


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
        cat_id = str(uuid.uuid4())
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO categories (id, user_id, name, type, icon)"
                " VALUES (%s, %s, 'Groceries', 'expense', '🍕')",
                [cat_id, user_id],
            )
            cursor.execute(
                "UPDATE transactions SET category_id = %s WHERE user_id = %s",
                [cat_id, user_id],
            )
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


@pytest.mark.django_db
class TestInstitutionDelete:
    def test_cascades(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.delete(f"/institutions/{accounts_data['institution_id']}/delete")
        assert response.status_code == 200
        assert b"Institution deleted!" in response.content

        # Verify accounts were cascade-deleted
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM accounts WHERE institution_id = %s",
                [accounts_data["institution_id"]],
            )
            assert cursor.fetchone()[0] == 0


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
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT is_dormant FROM accounts WHERE id = %s",
                [accounts_data["savings_id"]],
            )
            assert cursor.fetchone()[0] is True


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
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT health_config FROM accounts WHERE id = %s",
                [accounts_data["savings_id"]],
            )
            config = cursor.fetchone()[0]
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
        user_id = accounts_data["user_id"]
        cc_id = accounts_data["cc_id"]
        # statement_day=15, period=2026-03 covers 2026-02-16 to 2026-03-15
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, note, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 1234, 'EGP', %s, 'CC Charge', -1234)",
                [str(uuid.uuid4()), user_id, cc_id, date(2026, 3, 10)],
            )
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.get(f"/accounts/{cc_id}/statement?period=2026-03")
        assert response.status_code == 200
        assert b"CC Charge" in response.content

    def test_excludes_transaction_outside_billing_period(self, client, accounts_data):
        """Transaction outside the requested period is not shown."""  # gap: functional
        user_id = accounts_data["user_id"]
        cc_id = accounts_data["cc_id"]
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, note, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 999, 'EGP', %s, 'Old Charge', -999)",
                [str(uuid.uuid4()), user_id, cc_id, date(2026, 1, 5)],
            )
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.get(f"/accounts/{cc_id}/statement?period=2026-03")
        assert response.status_code == 200
        assert b"Old Charge" not in response.content

    def test_payment_history_shows_transfer_to_cc(self, client, accounts_data):
        """Transfer into the CC account appears in payment history."""  # gap: functional
        user_id = accounts_data["user_id"]
        cc_id = accounts_data["cc_id"]
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, counter_account_id, type, amount, currency, date, note, balance_delta)"
                " VALUES (%s, %s, %s, %s, 'transfer', 2000, 'EGP', %s, 'CC Payment', 2000)",
                [
                    str(uuid.uuid4()),
                    user_id,
                    accounts_data["savings_id"],
                    cc_id,
                    date(2026, 3, 10),
                ],
            )
        c = set_auth_cookie(client, accounts_data["session_token"])
        response = c.get(f"/accounts/{cc_id}/statement?period=2026-03")
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
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT icon, color FROM institutions WHERE name = %s AND user_id = %s",
                ["CIB - Commercial International Bank", accounts_data["user_id"]],
            )
            row = cursor.fetchone()
        assert row is not None
        assert row[0] == "cib.svg"
        assert row[1] == "#003DA5"

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
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT icon FROM institutions WHERE name = %s AND user_id = %s",
                ["Pocket Wallet", accounts_data["user_id"]],
            )
            row = cursor.fetchone()
        assert row is not None
        assert row[0] == "👛"

    def test_creates_institution_without_icon(self, client, accounts_data):
        c = set_auth_cookie(client, accounts_data["session_token"])
        resp = c.post(
            "/institutions/add",
            {"name": "My Local Bank", "type": "bank"},
        )
        assert resp.status_code == 200
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT icon, color FROM institutions WHERE name = %s AND user_id = %s",
                ["My Local Bank", accounts_data["user_id"]],
            )
            row = cursor.fetchone()
        assert row is not None
        assert row[0] is None
        assert row[1] is None


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
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT name FROM accounts WHERE user_id = %s AND type = 'prepaid'",
                [accounts_data["user_id"]],
            )
            row = cursor.fetchone()
        assert row is not None
        assert row[0] == "Test Bank - Prepaid"

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
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT name FROM accounts WHERE user_id = %s AND name = %s",
                [accounts_data["user_id"], "My Custom Account"],
            )
            row = cursor.fetchone()
        assert row is not None
