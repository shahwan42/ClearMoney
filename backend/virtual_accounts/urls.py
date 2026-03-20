"""
Virtual account URL patterns — page routes for envelope budgeting.

Static paths come before UUID paths to avoid being swallowed
by the <uuid:va_id> converter. Legacy /virtual-funds paths redirect
to /virtual-accounts for backwards compatibility.
"""

from django.urls import path

from virtual_accounts import views

urlpatterns = [
    # Static paths first
    path("virtual-accounts", views.virtual_accounts_page, name="virtual-accounts"),
    path("virtual-accounts/add", views.virtual_account_add, name="va-add"),
    # UUID paths
    path(
        "virtual-accounts/<uuid:va_id>", views.virtual_account_detail, name="va-detail"
    ),
    path(
        "virtual-accounts/<uuid:va_id>/archive",
        views.virtual_account_archive,
        name="va-archive",
    ),
    path(
        "virtual-accounts/<uuid:va_id>/allocate",
        views.virtual_account_allocate,
        name="va-allocate",
    ),
    path(
        "virtual-accounts/<uuid:va_id>/toggle-exclude",
        views.virtual_account_toggle_exclude,
        name="va-toggle-exclude",
    ),
    path(
        "virtual-accounts/<uuid:va_id>/edit-form",
        views.virtual_account_edit_form,
        name="va-edit-form",
    ),
    path(
        "virtual-accounts/<uuid:va_id>/edit",
        views.virtual_account_update,
        name="va-update",
    ),
    # Legacy redirects (/virtual-funds → /virtual-accounts)
    path("virtual-funds", views.virtual_funds_redirect, name="virtual-funds-redirect"),
    path(
        "virtual-funds/<uuid:va_id>",
        views.virtual_fund_detail_redirect,
        name="virtual-fund-detail-redirect",
    ),
]
