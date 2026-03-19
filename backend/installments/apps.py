"""
Installments app configuration.

Registers the installment plans Django app — like Laravel's InstallmentServiceProvider.
"""

from django.apps import AppConfig


class InstallmentsConfig(AppConfig):
    """Django app config for installment plan tracking."""

    name = "installments"
    default_auto_field = "django.db.models.BigAutoField"
