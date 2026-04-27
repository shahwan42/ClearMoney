"""
People view tests — HTTP-level tests for /people/* routes and /api/persons/* JSON API.
"""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING

import pytest

from conftest import SessionFactory, UserFactory, set_auth_cookie
from tests.factories import AccountFactory, CurrencyFactory, InstitutionFactory

if TYPE_CHECKING:
    from django.test import Client


@pytest.fixture
def people_view_data(db):
    """User + session + institution + EGP, USD, EUR accounts."""
    CurrencyFactory(code="EGP", name="Egyptian Pound", display_order=0)
    CurrencyFactory(code="USD", name="US Dollar", symbol="$", display_order=1)
    CurrencyFactory(code="EUR", name="Euro", display_order=2)
    user = UserFactory()
    session = SessionFactory(user=user)
    user_id = str(user.id)

    inst = InstitutionFactory(user_id=user.id, name="Test Bank", type="bank")
    egp_acct = AccountFactory(
        user_id=user.id,
        institution_id=inst.id,
        name="EGP Savings",
        type="savings",
        currency="EGP",
        current_balance=10000,
        initial_balance=10000,
    )
    usd_acct = AccountFactory(
        user_id=user.id,
        institution_id=inst.id,
        name="USD Savings",
        type="savings",
        currency="USD",
        current_balance=500,
        initial_balance=500,
    )
    eur_acct = AccountFactory(
        user_id=user.id,
        institution_id=inst.id,
        name="EUR Savings",
        type="savings",
        currency="EUR",
        current_balance=800,
        initial_balance=800,
    )

    yield {
        "user_id": user_id,
        "session_token": session.token,
        "egp_id": str(egp_acct.id),
        "usd_id": str(usd_acct.id),
        "eur_id": str(eur_acct.id),
    }


# ---------------------------------------------------------------------------
# People list page
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPeoplePage:
    def test_200_empty_state(self, client, people_view_data):
        c = set_auth_cookie(client, people_view_data["session_token"])
        response = c.get("/people")
        assert response.status_code == 200
        assert b"People" in response.content
        assert b"No people yet" in response.content

    def test_200_with_people(self, client, people_view_data):
        c = set_auth_cookie(client, people_view_data["session_token"])
        # Create a person first
        c.post("/people/add", {"name": "Ahmed"})
        response = c.get("/people")
        assert response.status_code == 200
        assert b"Ahmed" in response.content

    def test_unauthenticated_redirects(self, client):
        response = client.get("/people")
        assert response.status_code == 302
        assert "/login" in response.url


# ---------------------------------------------------------------------------
# Add person
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPeopleAdd:
    def test_creates_person_returns_html(self, client, people_view_data):
        c = set_auth_cookie(client, people_view_data["session_token"])
        response = c.post("/people/add", {"name": "Omar"})
        assert response.status_code == 200
        assert b"Omar" in response.content

    def test_empty_name_400(self, client, people_view_data):
        c = set_auth_cookie(client, people_view_data["session_token"])
        response = c.post("/people/add", {"name": ""})
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Loan recording
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPeopleLoan:
    def test_loan_out_returns_updated_list(self, client, people_view_data):
        c = set_auth_cookie(client, people_view_data["session_token"])
        # Create person
        c.post("/people/add", {"name": "Ali"})
        # Get person ID via API
        persons_resp = c.get("/api/persons")
        persons = json.loads(persons_resp.content)
        person_id = persons[0]["id"]

        response = c.post(
            f"/people/{person_id}/loan",
            {
                "amount": "1000",
                "account_id": people_view_data["egp_id"],
                "loan_type": "loan_out",
            },
        )
        assert response.status_code == 200
        assert b"1,000" in response.content

    def test_loan_in_returns_updated_list(self, client, people_view_data):
        c = set_auth_cookie(client, people_view_data["session_token"])
        c.post("/people/add", {"name": "Sara"})
        persons = json.loads(c.get("/api/persons").content)
        person_id = persons[0]["id"]

        response = c.post(
            f"/people/{person_id}/loan",
            {
                "amount": "2000",
                "account_id": people_view_data["egp_id"],
                "loan_type": "loan_in",
            },
        )
        assert response.status_code == 200
        assert b"2,000" in response.content

    def test_invalid_amount_returns_error_html(self, client, people_view_data):
        c = set_auth_cookie(client, people_view_data["session_token"])
        c.post("/people/add", {"name": "Test"})
        persons = json.loads(c.get("/api/persons").content)
        person_id = persons[0]["id"]

        response = c.post(
            f"/people/{person_id}/loan",
            {
                "amount": "",
                "account_id": people_view_data["egp_id"],
                "loan_type": "loan_out",
            },
        )
        assert response.status_code == 400

    def test_third_currency_loan_renders_generalized_balance(
        self, client, people_view_data
    ):
        c = set_auth_cookie(client, people_view_data["session_token"])
        c.post("/people/add", {"name": "Euro"})
        persons = json.loads(c.get("/api/persons").content)
        person_id = persons[0]["id"]

        response = c.post(
            f"/people/{person_id}/loan",
            {
                "amount": "125",
                "account_id": people_view_data["eur_id"],
                "loan_type": "loan_out",
            },
        )

        assert response.status_code == 200
        assert b"125" in response.content
        assert b"EUR" in response.content

    def test_memo_loan_no_account_uses_currency(self, client, people_view_data):
        c = set_auth_cookie(client, people_view_data["session_token"])
        c.post("/people/add", {"name": "MemoLender"})
        persons = json.loads(c.get("/api/persons").content)
        person_id = persons[0]["id"]

        response = c.post(
            f"/people/{person_id}/loan",
            {
                "amount": "750",
                "no_account": "1",
                "currency": "EGP",
                "loan_type": "loan_out",
            },
        )
        assert response.status_code == 200
        assert b"750" in response.content

    def test_memo_loan_missing_currency_returns_error(self, client, people_view_data):
        c = set_auth_cookie(client, people_view_data["session_token"])
        c.post("/people/add", {"name": "BadMemo"})
        persons = json.loads(c.get("/api/persons").content)
        person_id = persons[0]["id"]

        response = c.post(
            f"/people/{person_id}/loan",
            {"amount": "100", "no_account": "1", "loan_type": "loan_out"},
        )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Repayment
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPeopleRepay:
    def test_repayment_returns_updated_list(self, client, people_view_data):
        c = set_auth_cookie(client, people_view_data["session_token"])
        c.post("/people/add", {"name": "Repayer"})
        persons = json.loads(c.get("/api/persons").content)
        person_id = persons[0]["id"]

        # Lend 1000 first
        c.post(
            f"/people/{person_id}/loan",
            {
                "amount": "1000",
                "account_id": people_view_data["egp_id"],
                "loan_type": "loan_out",
            },
        )
        # Repay 500
        response = c.post(
            f"/people/{person_id}/repay",
            {
                "amount": "500",
                "account_id": people_view_data["egp_id"],
            },
        )
        assert response.status_code == 200
        assert b"500" in response.content


# ---------------------------------------------------------------------------
# Person detail page
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPersonDetail:
    def test_200_with_debt_summary(self, client, people_view_data):
        c = set_auth_cookie(client, people_view_data["session_token"])
        c.post("/people/add", {"name": "DetailTest"})
        persons = json.loads(c.get("/api/persons").content)
        person_id = persons[0]["id"]

        # Record a loan so there's data to show
        c.post(
            f"/people/{person_id}/loan",
            {
                "amount": "5000",
                "account_id": people_view_data["egp_id"],
                "loan_type": "loan_out",
            },
        )

        response = c.get(f"/people/{person_id}")
        assert response.status_code == 200
        assert b"DetailTest" in response.content
        assert b"Lent" in response.content
        assert b"5,000" in response.content

    def test_detail_page_shows_third_currency_balance(self, client, people_view_data):
        c = set_auth_cookie(client, people_view_data["session_token"])
        c.post("/people/add", {"name": "Euro Detail"})
        persons = json.loads(c.get("/api/persons").content)
        person_id = persons[0]["id"]

        c.post(
            f"/people/{person_id}/loan",
            {
                "amount": "125",
                "account_id": people_view_data["eur_id"],
                "loan_type": "loan_out",
            },
        )

        response = c.get(f"/people/{person_id}")
        assert response.status_code == 200
        assert b"Euro Detail" in response.content
        assert b"EUR" in response.content
        assert b"125" in response.content

    def test_detail_page_renders_dynamic_balance_rows_in_registry_order(
        self, client, people_view_data
    ):
        c = set_auth_cookie(client, people_view_data["session_token"])
        c.post("/people/add", {"name": "Order Detail"})
        persons = json.loads(c.get("/api/persons").content)
        person_id = persons[0]["id"]

        c.post(
            f"/people/{person_id}/loan",
            {
                "amount": "10",
                "account_id": people_view_data["eur_id"],
                "loan_type": "loan_out",
            },
        )
        c.post(
            f"/people/{person_id}/loan",
            {
                "amount": "20",
                "account_id": people_view_data["usd_id"],
                "loan_type": "loan_out",
            },
        )
        c.post(
            f"/people/{person_id}/loan",
            {
                "amount": "30",
                "account_id": people_view_data["egp_id"],
                "loan_type": "loan_out",
            },
        )

        response = c.get(f"/people/{person_id}")
        assert response.status_code == 200

        html = response.content.decode()
        egp_index = html.index('data-currency="EGP"')
        usd_index = html.index('data-currency="USD"')
        eur_index = html.index('data-currency="EUR"')
        assert egp_index < usd_index < eur_index

    def test_404_nonexistent(self, client, people_view_data):
        c = set_auth_cookie(client, people_view_data["session_token"])
        fake_id = str(uuid.uuid4())
        response = c.get(f"/people/{fake_id}")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# JSON API
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestPersonAPI:
    def test_list_empty(self, client, people_view_data):
        c = set_auth_cookie(client, people_view_data["session_token"])
        response = c.get("/api/persons")
        assert response.status_code == 200
        assert json.loads(response.content) == []

    def test_crud_lifecycle(self, client, people_view_data):
        c = set_auth_cookie(client, people_view_data["session_token"])

        # Create
        resp = c.post(
            "/api/persons",
            data=json.dumps({"name": "API Person"}),
            content_type="application/json",
        )
        assert resp.status_code == 201
        person = json.loads(resp.content)
        assert person["name"] == "API Person"
        pid = person["id"]

        # Get
        resp = c.get(f"/api/persons/{pid}")
        assert resp.status_code == 200
        assert json.loads(resp.content)["name"] == "API Person"

        # Update
        resp = c.put(
            f"/api/persons/{pid}",
            data=json.dumps({"name": "Updated Name", "note": "friend"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        assert json.loads(resp.content)["name"] == "Updated Name"

        # Delete
        resp = c.delete(f"/api/persons/{pid}")
        assert resp.status_code == 204

        # Verify gone
        resp = c.get(f"/api/persons/{pid}")
        assert resp.status_code == 404

    def test_loan_api(self, client, people_view_data):
        c = set_auth_cookie(client, people_view_data["session_token"])

        # Create person
        resp = c.post(
            "/api/persons",
            data=json.dumps({"name": "Loan API"}),
            content_type="application/json",
        )
        pid = json.loads(resp.content)["id"]

        # Record loan
        resp = c.post(
            f"/api/persons/{pid}/loan",
            data=json.dumps(
                {
                    "account_id": people_view_data["egp_id"],
                    "amount": 1500,
                    "type": "loan_out",
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 201
        tx = json.loads(resp.content)
        assert tx["type"] == "loan_out"
        assert tx["amount"] == 1500

    def test_repayment_api(self, client, people_view_data):
        c = set_auth_cookie(client, people_view_data["session_token"])

        # Create person + loan
        resp = c.post(
            "/api/persons",
            data=json.dumps({"name": "Repay API"}),
            content_type="application/json",
        )
        pid = json.loads(resp.content)["id"]
        c.post(
            f"/api/persons/{pid}/loan",
            data=json.dumps(
                {
                    "account_id": people_view_data["egp_id"],
                    "amount": 2000,
                    "type": "loan_out",
                }
            ),
            content_type="application/json",
        )

        # Record repayment
        resp = c.post(
            f"/api/persons/{pid}/repayment",
            data=json.dumps(
                {
                    "account_id": people_view_data["egp_id"],
                    "amount": 800,
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 201
        tx = json.loads(resp.content)
        assert tx["type"] == "loan_repayment"
        assert tx["amount"] == 800


# ---------------------------------------------------------------------------
# Loan API error paths
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestApiPersonLoanErrors:
    """Error-path tests for POST /api/persons/{id}/loan."""

    def _create_person(self, c: Client, people_view_data: dict[str, str]) -> str:
        """Helper — create a person via API and return its ID."""
        resp = c.post(
            "/api/persons",
            data=json.dumps({"name": "Loan Error Test"}),
            content_type="application/json",
        )
        pid: str = json.loads(resp.content)["id"]
        return pid

    def test_missing_account_id_returns_error(
        self, client: Client, people_view_data: dict[str, str]
    ) -> None:
        """Omitting account_id triggers a 400 from the service layer."""
        c = set_auth_cookie(client, people_view_data["session_token"])
        pid = self._create_person(c, people_view_data)

        resp = c.post(
            f"/api/persons/{pid}/loan",
            data=json.dumps({"amount": 500, "type": "loan_out"}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        body = json.loads(resp.content)
        assert "error" in body

    def test_zero_amount_returns_error(
        self, client: Client, people_view_data: dict[str, str]
    ) -> None:
        """amount=0 is rejected as non-positive."""
        c = set_auth_cookie(client, people_view_data["session_token"])
        pid = self._create_person(c, people_view_data)

        resp = c.post(
            f"/api/persons/{pid}/loan",
            data=json.dumps(
                {
                    "account_id": people_view_data["egp_id"],
                    "amount": 0,
                    "type": "loan_out",
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 400
        body = json.loads(resp.content)
        assert "error" in body
        assert "positive" in body["error"].lower()

    def test_invalid_loan_type_returns_error(
        self, client: Client, people_view_data: dict[str, str]
    ) -> None:
        """Invalid loan type triggers a 400 from the service layer."""
        c = set_auth_cookie(client, people_view_data["session_token"])
        pid = self._create_person(c, people_view_data)

        resp = c.post(
            f"/api/persons/{pid}/loan",
            data=json.dumps(
                {
                    "account_id": people_view_data["egp_id"],
                    "amount": 500,
                    "type": "invalid_type",
                }
            ),
            content_type="application/json",
        )
        assert resp.status_code == 400
        body = json.loads(resp.content)
        assert "error" in body


# ---------------------------------------------------------------------------
# Repayment API error paths
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestApiPersonRepaymentErrors:
    """Error-path tests for POST /api/persons/{id}/repayment."""

    def _create_person_with_loan(
        self, c: Client, people_view_data: dict[str, str]
    ) -> str:
        """Helper — create a person with an outstanding loan, return person ID."""
        resp = c.post(
            "/api/persons",
            data=json.dumps({"name": "Repay Error Test"}),
            content_type="application/json",
        )
        pid: str = json.loads(resp.content)["id"]
        c.post(
            f"/api/persons/{pid}/loan",
            data=json.dumps(
                {
                    "account_id": people_view_data["egp_id"],
                    "amount": 2000,
                    "type": "loan_out",
                }
            ),
            content_type="application/json",
        )
        return pid

    def test_missing_amount_returns_error(
        self, client: Client, people_view_data: dict[str, str]
    ) -> None:
        """Omitting amount defaults to 0, which the service rejects."""
        c = set_auth_cookie(client, people_view_data["session_token"])
        pid = self._create_person_with_loan(c, people_view_data)

        resp = c.post(
            f"/api/persons/{pid}/repayment",
            data=json.dumps({"account_id": people_view_data["egp_id"]}),
            content_type="application/json",
        )
        assert resp.status_code == 400
        body = json.loads(resp.content)
        assert "error" in body

    def test_nonexistent_person_returns_404(
        self, client: Client, people_view_data: dict[str, str]
    ) -> None:
        """Repayment to a non-existent person_id returns an error."""
        c = set_auth_cookie(client, people_view_data["session_token"])
        fake_pid = str(uuid.uuid4())

        resp = c.post(
            f"/api/persons/{fake_pid}/repayment",
            data=json.dumps(
                {
                    "account_id": people_view_data["egp_id"],
                    "amount": 500,
                }
            ),
            content_type="application/json",
        )
        # Service raises ValueError("Person not found") -> 400
        assert resp.status_code in (400, 404)
        body = json.loads(resp.content)
        assert "error" in body
