"""
Budget URL patterns — page routes for budget management.

Static paths come before UUID paths to avoid being swallowed
by the <uuid:budget_id> converter.
"""

from django.urls import path

from budgets import views

urlpatterns = [
    path("budgets", views.budgets_page, name="budgets"),
    path("budgets/add", views.budget_add, name="budget-add"),
    path("budgets/<uuid:budget_id>/delete", views.budget_delete, name="budget-delete"),
]
