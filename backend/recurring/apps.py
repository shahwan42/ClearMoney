"""Django app config for recurring — scheduled transaction rules.

Like Laravel's scheduled tasks
(app/Console/Kernel.php) — defines rules that fire on a schedule and create
transactions automatically or after user confirmation.
"""

from django.apps import AppConfig


class RecurringConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "recurring"
