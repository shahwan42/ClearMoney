"""
Exchange rates app configuration.

Registers the exchange rate history Django app — like Laravel's ExchangeRateServiceProvider.
"""

from django.apps import AppConfig


class ExchangeRatesConfig(AppConfig):
    """Django app config for exchange rate history viewing."""

    name = "exchange_rates"
    default_auto_field = "django.db.models.BigAutoField"
