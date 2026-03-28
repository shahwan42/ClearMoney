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
    path("budgets/total/set", views.total_budget_set, name="total-budget-set"),
    path("budgets/total/delete", views.total_budget_delete, name="total-budget-delete"),
    path("budgets/<uuid:budget_id>/", views.budget_detail, name="budget-detail"),
    path("budgets/<uuid:budget_id>/edit", views.budget_edit, name="budget-edit"),
    path("budgets/<uuid:budget_id>/delete", views.budget_delete, name="budget-delete"),
]
