"""
Push notifications app configuration.

Registers the push notifications Django app — like Laravel's PushServiceProvider.
"""

from django.apps import AppConfig


class PushConfig(AppConfig):
    """Django app config for push notification API endpoints."""

    name = "push"
    default_auto_field = "django.db.models.BigAutoField"
