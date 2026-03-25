"""
Dashboard view tests — HTTP-level tests for dashboard page and HTMX partials.
"""

from datetime import date

import pytest

from conftest import SessionFactory, UserFactory
from core.middleware import COOKIE_NAME
from tests.factories import (
    AccountFactory,
    CategoryFactory,
    InstitutionFactory,
    TransactionFactory,
)


@pytest.fixture
def dashboard_data(db):
    """User + session + institution + account + 3 transactions."""
    user = UserFactory()
    session = SessionFactory(user=user)
    institution = InstitutionFactory(user_id=user.id, name="Test Bank")
    account = AccountFactory(
        user_id=user.id,
        institution_id=institution.id,
        name="Main Savings",
        currency="EGP",
        current_balance=15000,
    )
    for i in range(3):
        TransactionFactory(
            user_id=user.id,
            account_id=account.id,
            type="expense",
            amount=100 + i * 50,
            currency="EGP",
            date=date(2026, 3, 10 + i),
            note=f"Expense {i}",
            balance_delta=-(100 + i * 50),
        )
    yield {
        "user_id": str(user.id),
        "session_token": session.token,
        "account_id": str(account.id),
    }


@pytest.fixture
def empty_user(db):
    """User + session with no accounts or transactions (empty state)."""
    user = UserFactory()
    session = SessionFactory(user=user)
    yield {"user_id": str(user.id), "session_token": session.token}


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
    category = CategoryFactory(
        user_id=dashboard_data["user_id"], name="Transport", type="expense"
    )
    TransactionFactory(
        user_id=dashboard_data["user_id"],
        account_id=dashboard_data["account_id"],
        type="expense",
        amount=50,
        currency="EGP",
        balance_delta=-50,
        category_id=category.id,
    )
    cookie = {"HTTP_COOKIE": f"{COOKIE_NAME}={dashboard_data['session_token']}"}
    response = client.get("/partials/recent-transactions", **cookie)
    content = response.content.decode()
    assert "Transport" in content


# ---------------------------------------------------------------------------
# GET /partials/people-summary — HTMX partial
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_people_summary_partial_200(client, dashboard_data):
    """GET /partials/people-summary returns 200."""
    cookie = {"HTTP_COOKIE": f"{COOKIE_NAME}={dashboard_data['session_token']}"}
    response = client.get("/partials/people-summary", **cookie)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET / — empty dashboard state (no accounts, transactions, or data)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboard_empty_user_renders_without_error(client, empty_user):
    # gap: state — user with no data at all must not crash any dashboard service
    cookie = {"HTTP_COOKIE": f"{COOKIE_NAME}={empty_user['session_token']}"}
    response = client.get("/", **cookie)
    assert response.status_code == 200
    content = response.content.decode()
    # Page should render (not 500) and show the welcome message
    assert "Welcome to ClearMoney" in content
    # No institution groups should be present
    assert "Test Bank" not in content
