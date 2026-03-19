"""
Investments app configuration.

Registers the investment tracking Django app — like Laravel's InvestmentServiceProvider.
"""

from django.apps import AppConfig


class InvestmentsConfig(AppConfig):
    """Django app config for investment portfolio tracking."""

    name = "investments"
    default_auto_field = "django.db.models.BigAutoField"
