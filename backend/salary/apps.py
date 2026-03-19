"""
Salary app configuration.

Registers the salary wizard Django app — like Laravel's SalaryServiceProvider.
"""

from django.apps import AppConfig


class SalaryConfig(AppConfig):
    """Django app config for the salary distribution wizard."""

    name = "salary"
    default_auto_field = "django.db.models.BigAutoField"
