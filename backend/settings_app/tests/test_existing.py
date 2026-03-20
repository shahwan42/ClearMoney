"""
Settings app tests — settings page rendering and CSV export.

Integration tests using @pytest.mark.django_db with the auth_user and
auth_cookie fixtures from conftest.py.
"""

import pytest

# ---------------------------------------------------------------------------
# GET /settings
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_settings_returns_200(client, auth_cookie):
    """Authenticated request to /settings returns 200."""
    response = client.get("/settings", **auth_cookie)
    assert response.status_code == 200


@pytest.mark.django_db
def test_settings_contains_key_elements(client, auth_cookie):
    """Settings page contains dark mode, export, notifications, and logout."""
    response = client.get("/settings", **auth_cookie)
    content = response.content.decode()
    assert "Dark Mode" in content
    assert "Export Transactions" in content
    assert "Push Notifications" in content
    assert "Log Out" in content


@pytest.mark.django_db
def test_settings_contains_quick_links(client, auth_cookie):
    """Settings page contains quick links to other features."""
    response = client.get("/settings", **auth_cookie)
    content = response.content.decode()
    assert "/budgets" in content
    assert "/investments" in content
    assert "/recurring" in content


@pytest.mark.django_db
def test_settings_redirects_without_auth(client):
    """Unauthenticated request redirects to /login."""
    response = client.get("/settings")
    assert response.status_code == 302
    assert response.url == "/login"


# ---------------------------------------------------------------------------
# GET /export/transactions
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_export_returns_csv(client, auth_cookie):
    """Export with valid dates returns CSV with correct headers."""
    response = client.get(
        "/export/transactions?from=2026-01-01&to=2026-03-31", **auth_cookie
    )
    assert response.status_code == 200
    assert response["Content-Type"] == "text/csv"
    assert "attachment" in response["Content-Disposition"]
    assert "transactions_" in response["Content-Disposition"]


@pytest.mark.django_db
def test_export_csv_header_row(client, auth_cookie):
    """CSV contains the expected header row."""
    response = client.get(
        "/export/transactions?from=2026-01-01&to=2026-03-31", **auth_cookie
    )
    first_line = response.content.decode().split("\r\n")[0]
    assert (
        first_line == "Date,Type,Amount,Currency,Account ID,Category ID,Note,Created At"
    )


@pytest.mark.django_db
def test_export_invalid_dates_returns_400(client, auth_cookie):
    """Invalid date parameters return 400."""
    response = client.get(
        "/export/transactions?from=invalid&to=also-invalid", **auth_cookie
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_export_missing_dates_returns_400(client, auth_cookie):
    """Missing date parameters return 400."""
    response = client.get("/export/transactions", **auth_cookie)
    assert response.status_code == 400


@pytest.mark.django_db
def test_export_redirects_without_auth(client):
    """Unauthenticated export redirects to /login."""
    response = client.get("/export/transactions?from=2026-01-01&to=2026-03-31")
    assert response.status_code == 302
