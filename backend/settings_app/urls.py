"""
Settings URL configuration.

Routes:
- /settings — settings page (dark mode, export, notifications, quick links)
- /settings/language — update user's language preference
- /export/transactions — CSV transaction export download
"""

from django.urls import path

from . import views, views_import

urlpatterns = [
    path("settings", views.settings_page, name="settings"),
    path("settings/language", views.set_language, name="set-language"),
    path(
        "settings/currencies", views.set_active_currencies, name="set-active-currencies"
    ),
    path(
        "settings/display-currency",
        views.set_display_currency,
        name="set-display-currency",
    ),
    path("settings/categories", views.categories_page, name="categories"),
    path("settings/categories/add", views.category_add, name="category-add"),
    path(
        "settings/categories/<uuid:cat_id>/update",
        views.category_update,
        name="category-update",
    ),
    path(
        "settings/categories/<uuid:cat_id>/archive",
        views.category_archive,
        name="category-archive",
    ),
    path(
        "settings/categories/<uuid:cat_id>/unarchive",
        views.category_unarchive,
        name="category-unarchive",
    ),
    path("settings/tags", views.tags_page, name="tags_settings"),
    path("settings/tags/add", views.tag_add, name="tag-add"),
    path("settings/tags/<uuid:tag_id>/update", views.tag_update, name="tag-update"),
    path("settings/tags/<uuid:tag_id>/delete", views.tag_delete, name="tag-delete"),
    path("settings/tags/merge", views.tag_merge, name="tag-merge"),
    path("export/transactions", views.export_transactions, name="export-transactions"),
    path("settings/import", views_import.import_upload, name="import-upload"),
    path(
        "settings/import/<str:import_id>/mapping",
        views_import.import_mapping,
        name="import-mapping",
    ),
    path(
        "settings/import/<str:import_id>/preview",
        views_import.import_preview,
        name="import-preview",
    ),
    path(
        "settings/import/<str:import_id>/summary",
        views_import.import_summary,
        name="import-summary",
    ),
]
