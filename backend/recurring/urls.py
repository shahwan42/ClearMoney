"""
Recurring rules URL patterns — page routes for /recurring*.

Static paths (add) come before UUID paths to avoid being
swallowed by the <uuid:rule_id> converter.
"""

from django.urls import path

from recurring import views

urlpatterns = [
    # Static paths first
    path("recurring", views.recurring_page, name="recurring"),
    path("recurring/add", views.recurring_add, name="recurring-add"),
    # UUID paths (confirm/skip before bare UUID to avoid capture)
    path(
        "recurring/<uuid:rule_id>/confirm",
        views.recurring_confirm,
        name="recurring-confirm",
    ),
    path(
        "recurring/<uuid:rule_id>/skip",
        views.recurring_skip,
        name="recurring-skip",
    ),
    path(
        "recurring/<uuid:rule_id>",
        views.recurring_delete,
        name="recurring-delete",
    ),
]
