"""
Dashboard URL configuration — home page and HTMX partials.
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
    path(
        "partials/net-worth",
        views.net_worth_partial,
        name="net-worth-partial",
    ),
    path(
        "partials/accounts",
        views.accounts_partial,
        name="accounts-partial",
    ),
    path(
        "dashboard/net-worth/<str:card_type>",
        views.net_worth_breakdown_partial,
        name="net-worth-breakdown",
    ),
]
