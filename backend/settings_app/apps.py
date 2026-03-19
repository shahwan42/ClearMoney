"""
Settings app — user settings page and CSV transaction export.

Port of Go's PageHandler.Settings() and ExportTransactions(). Serves:
- GET /settings — dark mode, export, push notifications, quick links, logout
- GET /export/transactions — CSV file download with date range filter

Named 'settings_app' (not 'settings') to avoid shadowing Django's settings module.
"""

from django.apps import AppConfig


class SettingsAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "settings_app"
