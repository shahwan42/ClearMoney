"""Fee Presets app — user-configurable fee templates (InstaPay, ATM, custom)."""

from django.apps import AppConfig


class FeePresetsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "fee_presets"
