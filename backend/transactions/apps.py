"""Django app configuration for the transactions app.

Port of Go's transaction handlers, service, and repository.
Handles all /transactions/*, /transfers/*, /exchange/*, /batch-entry,
/fawry-cashout, and /sync/transactions routes.
"""

from django.apps import AppConfig


class TransactionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "transactions"
