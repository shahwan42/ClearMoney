"""
Dashboard app — home page aggregating data from 10+ sources.

The most complex app in the Django backend — assembles net worth, accounts,
spending, CC summaries, budgets, streak, people, investments, and sparklines
into a single page.
"""

from django.apps import AppConfig


class DashboardConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "dashboard"
