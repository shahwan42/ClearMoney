"""Fee preset URL configuration.

Routes:
- /settings/fee-presets — management page
- /api/fee-presets — API for transaction forms
"""

from django.urls import path

from . import views

urlpatterns = [
    # Settings pages
    path("settings/fee-presets", views.fee_presets_page, name="fee-presets"),
    path(
        "settings/fee-presets/new-form",
        views.fee_preset_new_form,
        name="fee-preset-new-form",
    ),
    path("settings/fee-presets/add", views.fee_preset_add, name="fee-preset-add"),
    path(
        "settings/fee-presets/<uuid:preset_id>/update",
        views.fee_preset_update,
        name="fee-preset-update",
    ),
    path(
        "settings/fee-presets/<uuid:preset_id>/archive",
        views.fee_preset_archive,
        name="fee-preset-archive",
    ),
    path(
        "settings/fee-presets/<uuid:preset_id>/unarchive",
        views.fee_preset_unarchive,
        name="fee-preset-unarchive",
    ),
    # API endpoints
    path("api/fee-presets", views.api_fee_presets_for_currency, name="api-fee-presets"),
    path(
        "api/fee-presets/calculate",
        views.api_fee_preset_calculate,
        name="api-fee-preset-calculate",
    ),
]
