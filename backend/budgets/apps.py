"""
Budgets app — monthly spending limits per category with progress tracking.

Like Laravel's Budget module — handles /budgets/* routes for CRUD + spending display.
"""

from django.apps import AppConfig


class BudgetsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "budgets"
