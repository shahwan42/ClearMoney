"""
ClearMoney URL configuration.

Routes migrated features to their Django apps.
Go still handles all other routes — Caddy decides which app gets each request.
"""

from django.urls import include, path

urlpatterns = [
    path("", include("settings_app.urls")),
    path("", include("reports.urls")),
]
