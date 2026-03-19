"""
Auth app configuration.

Registers the auth Django app — like Laravel's AuthServiceProvider.
"""

from django.apps import AppConfig


class AuthAppConfig(AppConfig):
    """Django app config for magic link authentication."""

    name = "auth_app"
    default_auto_field = "django.db.models.BigAutoField"
