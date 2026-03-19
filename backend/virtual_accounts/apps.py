"""
Django app config for virtual_accounts — envelope budgeting system.

Like Laravel's ServiceProvider for the VirtualAccount module.
Virtual accounts let users earmark money for goals without physically
moving funds between bank accounts.
"""

from django.apps import AppConfig


class VirtualAccountsConfig(AppConfig):
    """App configuration for virtual accounts (envelope budgeting)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "virtual_accounts"
