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
    path("budgets/add-form", views.budget_add_form, name="budget-add-form"),
    path(
        "budgets/copy-last-month",
        views.budget_copy_last_month,
        name="budget-copy-last-month",
    ),
    path("budgets/total/set", views.total_budget_set, name="total-budget-set"),
    path(
        "budgets/total/<str:currency>/edit-form",
        views.total_budget_edit_form,
        name="total-budget-edit-form",
    ),
    path("budgets/total/delete", views.total_budget_delete, name="total-budget-delete"),
    path("budgets/<uuid:budget_id>/", views.budget_detail, name="budget-detail"),
    path(
        "budgets/<uuid:budget_id>/edit-form",
        views.budget_edit_form,
        name="budget-edit-form",
    ),
    path("budgets/<uuid:budget_id>/edit", views.budget_edit, name="budget-edit"),
    path("budgets/<uuid:budget_id>/delete", views.budget_delete, name="budget-delete"),
]
