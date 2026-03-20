"""
Core app — shared models, auth middleware, template tags, and HTMX helpers.

The foundation layer used by all other Django apps. Contains:
- Models mapping to the PostgreSQL schema
- GoSessionAuthMiddleware for session-based authentication
- Template filters (format_egp, format_currency, etc.)
- AuthenticatedRequest type for type-safe view signatures
"""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
