"""
Accounts & Institutions URL configuration.

Handles all /accounts/* and /institutions/* HTML + HTMX routes.
"""

from django.urls import path

from accounts import views

urlpatterns = [
    # --- Pages ---
    path("accounts", views.accounts_list, name="accounts"),
    # Static sub-paths MUST come before <uuid:id> to avoid being swallowed
    path("accounts/add-form", views.account_add_form, name="account-add-form"),
    path("accounts/form", views.account_form, name="account-form"),
    path("accounts/add", views.account_add, name="account-add"),
    path("accounts/list", views.institution_list_partial, name="institution-list"),
    path(
        "accounts/institution-form",
        views.institution_form_partial,
        name="institution-form",
    ),
    path(
        "accounts/institution-presets",
        views.institution_presets,
        name="institution-presets",
    ),
    path("accounts/empty", views.empty_partial, name="empty-partial"),
    path("accounts/reorder", views.accounts_reorder, name="accounts-reorder"),
    # UUID sub-paths
    path("accounts/<uuid:id>", views.account_detail, name="account-detail"),
    path(
        "accounts/<uuid:id>/statement", views.credit_card_statement, name="cc-statement"
    ),
    path(
        "accounts/<uuid:id>/edit-form",
        views.account_edit_form,
        name="account-edit-form",
    ),
    path("accounts/<uuid:id>/edit", views.account_update, name="account-update"),
    path("accounts/<uuid:id>/delete", views.account_delete, name="account-delete"),
    path(
        "accounts/<uuid:id>/balance-check",
        views.balance_check_page,
        name="account-balance-check",
    ),
    path(
        "accounts/<uuid:id>/balance-check/submit",
        views.balance_check_submit,
        name="account-balance-check-submit",
    ),
    path(
        "accounts/<uuid:id>/balance-check/correct",
        views.balance_check_correct,
        name="account-balance-check-correct",
    ),
    path(
        "accounts/<uuid:id>/reconcile", views.reconcile_page, name="account-reconcile"
    ),
    path(
        "accounts/<uuid:id>/reconcile/submit",
        views.reconcile_submit,
        name="account-reconcile-submit",
    ),
    path("accounts/<uuid:id>/dormant", views.toggle_dormant, name="toggle-dormant"),
    path("accounts/<uuid:id>/health", views.health_update, name="health-update"),
    # --- Institutions ---
    path("institutions/add", views.institution_add, name="institution-add"),
    path(
        "institutions/reorder", views.institutions_reorder, name="institutions-reorder"
    ),
    path(
        "institutions/<uuid:id>/edit-form",
        views.institution_edit_form,
        name="institution-edit-form",
    ),
    path(
        "institutions/<uuid:id>/update",
        views.institution_update,
        name="institution-update",
    ),
    path(
        "institutions/<uuid:id>/delete-confirm",
        views.institution_delete_confirm,
        name="institution-delete-confirm",
    ),
    path(
        "institutions/<uuid:id>/delete",
        views.institution_delete,
        name="institution-delete",
    ),
    # --- JSON API routes ---
    path(
        "api/institutions", views.api_institution_list_create, name="api-institutions"
    ),
    path(
        "api/institutions/<uuid:inst_id>",
        views.api_institution_detail,
        name="api-institution-detail",
    ),
    path("api/system-banks", views.api_system_banks, name="api-system-banks"),
    path("api/accounts", views.api_account_list_create, name="api-accounts"),
    path(
        "api/accounts/<uuid:account_id>",
        views.api_account_detail,
        name="api-account-detail",
    ),
]
