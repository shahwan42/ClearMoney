"""
Categories app — manages expense/income categories for transactions.

Port of Go's CategoryService + CategoryRepo + CategoryHandler.
Like Laravel's Category module — handles /api/categories/* JSON API.
"""

from django.apps import AppConfig


class CategoriesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "categories"
