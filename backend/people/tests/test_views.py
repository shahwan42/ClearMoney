"""
People view tests — HTTP-level tests for /people/* routes and /api/persons/* JSON API.

Uses raw SQL fixtures for PostgreSQL enum columns.
"""

import json
import uuid

import pytest
from django.db import connection

from conftest import SessionFactory, UserFactory, set_auth_cookie
from core.models import Session, User


@pytest.fixture
def people_view_data(db):
    """User + session + institution + EGP account (10000) + USD account (500)."""
    user = UserFactory()
    session = SessionFactory(user=user)
    user_id = str(user.id)
    inst_id = str(uuid.uuid4())
    egp_id = str(uuid.uuid4())
    usd_id = str(uuid.uuid4())

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
            "INSERT INTO accounts (id, user_id, institution_id, name, type, currency,"
            " current_balance, initial_balance)"
            " VALUES (%s, %s, %s, %s, 'savings', 'USD', %s, %s)",
            [usd_id, user_id, inst_id, "USD Savings", 500, 500],
        )

    yield {
        "user_id": user_id,
        "session_token": session.token,
        "egp_id": egp_id,
        "usd_id": usd_id,
    }

    # Cleanup
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM transactions WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM persons WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM accounts WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM institutions WHERE user_id = %s", [user_id])
    Session.objects.filter(user=user).delete()
    User.objects.filter(id=user.id).delete()


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
