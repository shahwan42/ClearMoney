"""
ClearMoney URL configuration.

Routes migrated features to their Django apps.
"""

from django.http import HttpRequest, HttpResponse
from django.urls import include, path

# Custom error handlers — match app design instead of Django's defaults
handler404 = "core.views.custom_404"
handler500 = "core.views.custom_500"
handler429 = "core.views.ratelimited_error"


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
    path("", include("investments.urls")),
    path("", include("exchange_rates.urls")),
    path("", include("push.urls")),
    path("", include("categories.urls")),
    path("", include("auth_app.urls")),
]
