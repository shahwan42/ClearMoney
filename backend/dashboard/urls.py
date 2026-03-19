"""
Dashboard URL configuration — home page and HTMX partials.

Routes migrated from Go:
- GET /  → home page (was PageHandler.Home)
- GET /partials/recent-transactions → HTMX partial
- GET /partials/people-summary → HTMX partial
"""

from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path(
        "partials/recent-transactions",
        views.recent_transactions_partial,
        name="recent-transactions",
    ),
    path(
        "partials/people-summary",
        views.people_summary_partial,
        name="people-summary",
    ),
]
