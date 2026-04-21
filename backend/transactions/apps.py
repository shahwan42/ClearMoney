"""Django app configuration for the transactions app.

Handles all /transactions/*, /transfers/*, /exchange/*, /batch-entry,
and /sync/transactions routes.
"""

from django.apps import AppConfig


class TransactionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "transactions"
