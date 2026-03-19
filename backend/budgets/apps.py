"""
Budgets app — monthly spending limits per category with progress tracking.

Port of Go's BudgetService + budget page handlers (pages.go:3210–3263).
Like Laravel's Budget module — handles /budgets/* routes for CRUD + spending display.
"""

from django.apps import AppConfig


class BudgetsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "budgets"
