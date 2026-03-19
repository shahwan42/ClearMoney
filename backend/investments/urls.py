"""
Investment URL patterns — routes for /investments*.

Static path must come before UUID captures to avoid being swallowed.
"""

from django.urls import path

from investments import views

urlpatterns = [
    path("investments", views.investments_page, name="investments"),
    path("investments/add", views.investment_add, name="investment-add"),
    path(
        "investments/<uuid:id>/update",
        views.investment_update,
        name="investment-update",
    ),
    path(
        "investments/<uuid:id>/delete",
        views.investment_delete,
        name="investment-delete",
    ),
]
