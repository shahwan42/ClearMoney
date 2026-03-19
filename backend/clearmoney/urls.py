"""
ClearMoney URL configuration.

Routes migrated features to their Django apps.
Go still handles all other routes — Caddy decides which app gets each request.
"""

from django.http import HttpRequest, HttpResponse
from django.urls import include, path


def healthz(request: HttpRequest) -> HttpResponse:
    """Simple health check for Playwright webServer readiness probe."""
    return HttpResponse("ok")


urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path("", include("dashboard.urls")),
    path("", include("settings_app.urls")),
    path("", include("reports.urls")),
    path("", include("accounts.urls")),
    path("", include("transactions.urls")),
    path("", include("people.urls")),
    path("", include("budgets.urls")),
    path("", include("virtual_accounts.urls")),
    path("", include("recurring.urls")),
]
