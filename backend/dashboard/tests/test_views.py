"""
Dashboard view tests — HTTP-level tests for dashboard page and HTMX partials.

Fixtures create test data via raw SQL, tests hit endpoints via the Django test client.
"""

import uuid
from datetime import date

import pytest
from django.db import connection

from conftest import SessionFactory, UserFactory
from core.middleware import COOKIE_NAME
from core.models import Session, User


@pytest.fixture
def dashboard_data(db):
    """User + session + institution + 2 accounts + 3 transactions.

    Creates minimal data for the dashboard to render. Yields dict with
    user_id and session_token. Cleans up on teardown.
    """
    user = UserFactory()
    session = SessionFactory(user=user)
    user_id = str(user.id)
    inst_id = str(uuid.uuid4())
    account_id = str(uuid.uuid4())

    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO institutions (id, user_id, name) VALUES (%s, %s, %s)",
            [inst_id, user_id, "Test Bank"],
        )
        cursor.execute(
            "INSERT INTO accounts (id, user_id, institution_id, name, type, currency, current_balance)"
            " VALUES (%s, %s, %s, %s, 'savings', 'EGP', %s)",
            [account_id, user_id, inst_id, "Main Savings", 15000],
        )
        for i in range(3):
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount, currency, date, note)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                [
                    str(uuid.uuid4()),
                    user_id,
                    account_id,
                    "expense",
                    100 + i * 50,
                    "EGP",
                    date(2026, 3, 10 + i),
                    f"Expense {i}",
                ],
            )

    yield {"user_id": user_id, "session_token": session.token}

    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM transactions WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM accounts WHERE user_id = %s", [user_id])
        cursor.execute("DELETE FROM institutions WHERE user_id = %s", [user_id])
    Session.objects.filter(user=user).delete()
    User.objects.filter(id=user.id).delete()


@pytest.fixture
def empty_user(db):
    """User + session with no accounts or transactions (empty state)."""
    user = UserFactory()
    session = SessionFactory(user=user)

    yield {"user_id": str(user.id), "session_token": session.token}

    Session.objects.filter(user=user).delete()
    User.objects.filter(id=user.id).delete()


# ---------------------------------------------------------------------------
# GET / — dashboard page
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboard_returns_200(client, dashboard_data):
    """Authenticated GET / returns 200."""
    cookie = {"HTTP_COOKIE": f"{COOKIE_NAME}={dashboard_data['session_token']}"}
    response = client.get("/", **cookie)
    assert response.status_code == 200


@pytest.mark.django_db
def test_dashboard_contains_net_worth(client, dashboard_data):
    """Dashboard HTML contains 'Net Worth' heading."""
    cookie = {"HTTP_COOKIE": f"{COOKIE_NAME}={dashboard_data['session_token']}"}
    response = client.get("/", **cookie)
    content = response.content.decode()
    assert "Net Worth" in content


@pytest.mark.django_db
def test_dashboard_contains_accounts(client, dashboard_data):
    """Dashboard HTML contains the test account name."""
    cookie = {"HTTP_COOKIE": f"{COOKIE_NAME}={dashboard_data['session_token']}"}
    response = client.get("/", **cookie)
    content = response.content.decode()
    assert "Main Savings" in content


@pytest.mark.django_db
def test_dashboard_empty_state(client, empty_user):
    """User with no accounts sees welcome message."""
    cookie = {"HTTP_COOKIE": f"{COOKIE_NAME}={empty_user['session_token']}"}
    response = client.get("/", **cookie)
    content = response.content.decode()
    assert "Welcome to ClearMoney" in content


@pytest.mark.django_db
def test_dashboard_redirects_without_auth(client):
    """Unauthenticated GET / redirects to /login."""
    response = client.get("/")
    assert response.status_code == 302
    assert response.url == "/login"


# ---------------------------------------------------------------------------
# GET /partials/recent-transactions — HTMX partial
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_recent_transactions_partial_200(client, dashboard_data):
    """GET /partials/recent-transactions returns 200."""
    cookie = {"HTTP_COOKIE": f"{COOKIE_NAME}={dashboard_data['session_token']}"}
    response = client.get("/partials/recent-transactions", **cookie)
    assert response.status_code == 200


@pytest.mark.django_db
def test_recent_transactions_contains_data(client, dashboard_data):
    """Partial contains transaction note text."""
    cookie = {"HTTP_COOKIE": f"{COOKIE_NAME}={dashboard_data['session_token']}"}
    response = client.get("/partials/recent-transactions", **cookie)
    content = response.content.decode()
    assert "Expense" in content


@pytest.mark.django_db
def test_recent_transactions_rows_have_no_card_styling(client, dashboard_data):
    # gap: functional — compact=True removes bg-white/rounded-xl/shadow-sm card classes
    cookie = {"HTTP_COOKIE": f"{COOKIE_NAME}={dashboard_data['session_token']}"}
    response = client.get("/partials/recent-transactions", **cookie)
    content = response.content.decode()
    # shadow-sm only appears on card-style rows, not compact rows
    assert "shadow-sm" not in content


@pytest.mark.django_db
def test_recent_transactions_rows_have_no_kebab_menu(client, dashboard_data):
    # gap: functional — hide_kebab=True removes kebab trigger from dashboard rows
    cookie = {"HTTP_COOKIE": f"{COOKIE_NAME}={dashboard_data['session_token']}"}
    response = client.get("/partials/recent-transactions", **cookie)
    content = response.content.decode()
    assert "data-kebab-trigger" not in content


@pytest.mark.django_db
def test_dashboard_includes_tx_detail_bottom_sheet(client, dashboard_data):
    # gap: state — bottom sheet include must be present for row clicks to work
    cookie = {"HTTP_COOKIE": f"{COOKIE_NAME}={dashboard_data['session_token']}"}
    response = client.get("/", **cookie)
    content = response.content.decode()
    assert 'id="tx-detail-sheet"' in content


@pytest.mark.django_db
def test_recent_transactions_shows_category_name(client, dashboard_data):
    # gap: data — dashboard rows show category name when category is set
    cat_id = str(uuid.uuid4())
    tx_id = str(uuid.uuid4())
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO categories (id, user_id, name, type) VALUES (%s, %s, %s, %s)",
                [cat_id, dashboard_data["user_id"], "Transport", "expense"],
            )
            cursor.execute(
                "SELECT id FROM accounts WHERE user_id = %s LIMIT 1",
                [dashboard_data["user_id"]],
            )
            acct_id = cursor.fetchone()[0]
            cursor.execute(
                "INSERT INTO transactions (id, user_id, account_id, type, amount,"
                " currency, date, category_id, balance_delta)"
                " VALUES (%s, %s, %s, 'expense', 50, 'EGP', CURRENT_DATE, %s, -50)",
                [tx_id, dashboard_data["user_id"], acct_id, cat_id],
            )
        cookie = {"HTTP_COOKIE": f"{COOKIE_NAME}={dashboard_data['session_token']}"}
        response = client.get("/partials/recent-transactions", **cookie)
        content = response.content.decode()
        assert "Transport" in content
    finally:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM transactions WHERE id = %s", [tx_id])
            cursor.execute("DELETE FROM categories WHERE id = %s", [cat_id])


# ---------------------------------------------------------------------------
# GET /partials/people-summary — HTMX partial
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_people_summary_partial_200(client, dashboard_data):
    """GET /partials/people-summary returns 200."""
    cookie = {"HTTP_COOKIE": f"{COOKIE_NAME}={dashboard_data['session_token']}"}
    response = client.get("/partials/people-summary", **cookie)
    assert response.status_code == 200
