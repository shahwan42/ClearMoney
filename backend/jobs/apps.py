"""
Django app config for the jobs app — background tasks as management commands.

Like Laravel's app/Console/Commands/ or
Django's standard management commands. Each job is a standalone command that
can be run via `manage.py <command>` or scheduled via Docker cron.
"""

from django.apps import AppConfig


class JobsConfig(AppConfig):
    """Configuration for the jobs app — no models, no migrations."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "jobs"
