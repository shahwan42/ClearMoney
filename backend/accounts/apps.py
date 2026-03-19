"""
Accounts app — CRUD for bank accounts, credit cards, and institutions.

Port of Go's account/institution handlers, services, and repositories.
Like Laravel's Account module — handles the /accounts/* and /institutions/* routes.
"""

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
