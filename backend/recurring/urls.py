"""
Budget URL patterns — page routes for budget management.

Static paths come before UUID paths to avoid being swallowed
by the <uuid:budget_id> converter.
"""

from django.urls import path

from recurring import views

urlpatterns = [
    path("recurring", views.recurring_page, name="recurring"),
    path("recurring/calendar", views.recurring_calendar, name="recurring-calendar"),
    path("recurring/add", views.recurring_add, name="recurring-add"),
    path("recurring/form", views.recurring_form, name="recurring-form"),
    # UUID paths (confirm/skip before bare UUID to avoid capture)
    path(
        "recurring/<uuid:rule_id>/confirm",
        views.recurring_confirm,
        name="recurring-confirm",
    ),
    path(
        "recurring/<uuid:rule_id>/confirm/form",
        views.recurring_confirm_form,
        name="recurring-confirm-form",
    ),
    path(
        "recurring/confirm-all",
        views.recurring_confirm_all,
        name="recurring-confirm-all",
    ),
    path(
        "recurring/<uuid:rule_id>/skip",
        views.recurring_skip,
        name="recurring-skip",
    ),
    path(
        "recurring/<uuid:rule_id>/edit",
        views.recurring_edit_form,
        name="recurring-edit-form",
    ),
    path(
        "recurring/<uuid:rule_id>/update",
        views.recurring_update,
        name="recurring-update",
    ),
    path(
        "recurring/<uuid:rule_id>",
        views.recurring_delete,
        name="recurring-delete",
    ),
]
