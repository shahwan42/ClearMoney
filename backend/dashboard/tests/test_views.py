"""
Dashboard view tests — HTTP-level tests for dashboard page and HTMX partials.
"""

from datetime import date, timedelta

import pytest
from django.utils import timezone

from conftest import SessionFactory, UserFactory, set_auth_cookie
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
    # gap: functional — compact=True removes bg-white/rounded-xl/shadow-sm card classes from ROWS
    cookie = {"HTTP_COOKIE": f"{COOKIE_NAME}={dashboard_data['session_token']}"}
    response = client.get("/partials/recent-transactions", **cookie)
    content = response.content.decode()
    # The section container HAS shadow-sm now, but the rows should NOT have it.
    # We verify that shadow-sm is NOT present multiple times (i.e. not on rows).
    # Each transaction row would have added one shadow-sm if not compact.
    # There are 3 transactions in dashboard_data + 1 container = 4 if bug exists.
    assert content.count("shadow-sm") == 1


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
        user_id=dashboard_data["user_id"], name={"en": "Transport"}, type="expense"
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


# ---------------------------------------------------------------------------
# Dashboard section IDs for OOB swap targets
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDashboardSectionIds:
    """Dashboard sections have OOB-targetable id attributes."""

    def test_net_worth_has_id(self, client, dashboard_data):
        cookie = {"HTTP_COOKIE": f"{COOKIE_NAME}={dashboard_data['session_token']}"}
        resp = client.get("/", **cookie)
        assert 'id="dashboard-net-worth"' in resp.content.decode()

    def test_accounts_has_id(self, client, dashboard_data):
        cookie = {"HTTP_COOKIE": f"{COOKIE_NAME}={dashboard_data['session_token']}"}
        resp = client.get("/", **cookie)
        assert 'id="dashboard-accounts"' in resp.content.decode()

    def test_sections_have_aria_live(self, client, dashboard_data):
        cookie = {"HTTP_COOKIE": f"{COOKIE_NAME}={dashboard_data['session_token']}"}
        resp = client.get("/", **cookie)
        content = resp.content.decode()
        # Both net worth and accounts wrappers should have aria-live
        assert content.count('aria-live="polite"') >= 2


# ---------------------------------------------------------------------------
# GET /dashboard/net-worth/<card_type> — breakdown partial
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestNetWorthBreakdownView:
    """Net worth breakdown bottom sheet partial."""

    def test_liquid_cash_returns_200(self, client, dashboard_data):
        cookie = {"HTTP_COOKIE": f"{COOKIE_NAME}={dashboard_data['session_token']}"}
        resp = client.get("/dashboard/net-worth/liquid_cash", **cookie)
        assert resp.status_code == 200
        assert b"Liquid Cash" in resp.content

    def test_all_four_types_work(self, client, dashboard_data):
        cookie = {"HTTP_COOKIE": f"{COOKIE_NAME}={dashboard_data['session_token']}"}
        for card_type in ["liquid_cash", "credit_used", "credit_available", "debt"]:
            resp = client.get(f"/dashboard/net-worth/{card_type}", **cookie)
            assert resp.status_code == 200

    def test_invalid_type_returns_400(self, client, dashboard_data):
        cookie = {"HTTP_COOKIE": f"{COOKIE_NAME}={dashboard_data['session_token']}"}
        resp = client.get("/dashboard/net-worth/invalid", **cookie)
        assert resp.status_code == 400

    def test_requires_auth(self, client):
        resp = client.get("/dashboard/net-worth/liquid_cash")
        assert resp.status_code == 302

    def test_dashboard_includes_nw_breakdown_sheet(self, client, dashboard_data):
        cookie = {"HTTP_COOKIE": f"{COOKIE_NAME}={dashboard_data['session_token']}"}
        resp = client.get("/", **cookie)
        assert b'id="nw-breakdown-sheet"' in resp.content

    def test_subcards_are_tappable(self, client, dashboard_data):
        cookie = {"HTTP_COOKIE": f"{COOKIE_NAME}={dashboard_data['session_token']}"}
        resp = client.get("/", **cookie)
        content = resp.content.decode()
        assert 'role="button"' in content
        assert "View Liquid Cash breakdown" in content


# ---------------------------------------------------------------------------
# Streak card styling
# ---------------------------------------------------------------------------


@pytest.fixture
def streak_data(db):
    """User with transactions today + yesterday → 2-day streak."""
    user = UserFactory()
    session = SessionFactory(user=user)
    inst = InstitutionFactory(user_id=user.id, name="Test Bank")
    account = AccountFactory(
        user_id=user.id,
        institution_id=inst.id,
        name="EGP Savings",
        currency="EGP",
        current_balance=10000,
    )
    today = timezone.now().date()
    for days_ago in range(2):
        TransactionFactory(
            user_id=user.id,
            account_id=account.id,
            date=today - timedelta(days=days_ago),
            amount=100,
            balance_delta=-100,
        )
    return {"session_token": session.token}


@pytest.mark.django_db
class TestMutedStreakCard:
    """Streak card uses muted styling, no gradient."""

    def test_no_gradient_classes(self, client, streak_data):
        cookie = {"HTTP_COOKIE": f"{COOKIE_NAME}={streak_data['session_token']}"}
        resp = client.get("/", **cookie)
        content = resp.content.decode()
        assert "from-amber-50" not in content
        assert "to-orange-50" not in content

    def test_streak_shows_day_streak_format(self, client, streak_data):
        cookie = {"HTTP_COOKIE": f"{COOKIE_NAME}={streak_data['session_token']}"}
        resp = client.get("/", **cookie)
        content = resp.content.decode()
        assert "day streak" in content

    def test_streak_shows_this_week(self, client, streak_data):
        cookie = {"HTTP_COOKIE": f"{COOKIE_NAME}={streak_data['session_token']}"}
        resp = client.get("/", **cookie)
        content = resp.content.decode()
        assert "this week" in content

    def test_streak_hidden_when_zero(self, client, empty_user):
        cookie = {"HTTP_COOKIE": f"{COOKIE_NAME}={empty_user['session_token']}"}
        resp = client.get("/", **cookie)
        content = resp.content.decode()
        assert "day streak" not in content


# ---------------------------------------------------------------------------
# Loading progress bar
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestLoadingProgressBar:
    """Base template includes loading progress bar."""

    def test_progress_bar_in_dashboard(self, client, dashboard_data):
        cookie = {"HTTP_COOKIE": f"{COOKIE_NAME}={dashboard_data['session_token']}"}
        resp = client.get("/", **cookie)
        content = resp.content.decode()
        assert 'id="page-progress"' in content
        assert 'role="progressbar"' in content
        assert 'aria-label="Page loading"' in content


@pytest.mark.django_db
class TestSpendingDateRangeLabel:
    """Spending section shows explicit date range (e.g. 'Mar 1–25') not just 'This month'."""

    def test_spending_partial_shows_date_range(self, client, dashboard_data):
        """Dashboard home shows actual date range label like 'Mar 1–25'."""
        from core.middleware import COOKIE_NAME

        cookie = {"HTTP_COOKIE": f"{COOKIE_NAME}={dashboard_data['session_token']}"}
        resp = client.get("/", **cookie)
        content = resp.content.decode()
        # Should show month abbreviation like "Jan", "Feb", "Mar" in date range context
        # Pattern: "Mar 1" or "Jan 1" etc.
        import re

        assert re.search(
            r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}", content
        )


@pytest.mark.django_db
class TestMoreMenuDiscoverability:
    """More menu button in bottom nav has visual indicators of expandability."""

    def test_more_button_has_chevron_indicator(self, client, dashboard_data) -> None:
        """More menu button includes a visual caret/chevron to hint it opens a sheet."""
        c = set_auth_cookie(client, dashboard_data["session_token"])
        resp = c.get("/")
        assert resp.status_code == 200
        content = resp.content.decode()
        # The More button area should contain a chevron-up indicator
        assert (
            "chevron" in content.lower()
            or "M5 15l7-7 7 7" in content
            or "M19 9l-7 7-7-7" in content
        )


# ---------------------------------------------------------------------------
# GET /dashboard/partials/net-worth and /dashboard/partials/accounts
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestDashboardPartials:
    """Dashboard partial endpoints for lazy-load OOB swaps (quick-entry)."""

    def test_net_worth_partial_returns_200_for_authenticated(
        self, client, dashboard_data
    ):
        """GET /partials/net-worth returns 200 for authenticated user."""
        cookie = {"HTTP_COOKIE": f"{COOKIE_NAME}={dashboard_data['session_token']}"}
        response = client.get("/partials/net-worth", **cookie)
        assert response.status_code == 200

    def test_accounts_partial_returns_200_for_authenticated(
        self, client, dashboard_data
    ):
        """GET /partials/accounts returns 200 for authenticated user."""
        cookie = {"HTTP_COOKIE": f"{COOKIE_NAME}={dashboard_data['session_token']}"}
        response = client.get("/partials/accounts", **cookie)
        assert response.status_code == 200

    def test_net_worth_partial_redirects_unauthenticated(self, client):
        """GET /partials/net-worth redirects to /login when unauthenticated."""
        response = client.get("/partials/net-worth")
        assert response.status_code == 302
        assert response.url == "/login"

    def test_accounts_partial_redirects_unauthenticated(self, client):
        """GET /partials/accounts redirects to /login when unauthenticated."""
        response = client.get("/partials/accounts")
        assert response.status_code == 302
        assert response.url == "/login"

    def test_net_worth_partial_contains_data(self, client, dashboard_data):
        """Net worth partial contains balance information."""
        cookie = {"HTTP_COOKIE": f"{COOKIE_NAME}={dashboard_data['session_token']}"}
        response = client.get("/dashboard/partials/net-worth", **cookie)
        content = response.content.decode()
        # Should contain some net worth content (balance, sparkline, etc)
        assert len(content) > 100  # Verify it's not empty

    def test_accounts_partial_contains_data(self, client, dashboard_data):
        """Accounts partial contains account information."""
        cookie = {"HTTP_COOKIE": f"{COOKIE_NAME}={dashboard_data['session_token']}"}
        response = client.get("/partials/accounts", **cookie)
        content = response.content.decode()
        # Should contain account name from fixture
        assert "Main Savings" in content
