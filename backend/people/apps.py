"""
People app — tracks personal lending and borrowing with multi-currency balances.

Like Laravel's Person module — handles /people/* routes and /api/persons/* JSON API.
"""

from django.apps import AppConfig


class PeopleConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "people"
