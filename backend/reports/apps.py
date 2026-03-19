"""
Reports app — monthly spending reports with donut and bar charts.

Port of Go's PageHandler.Reports() and ReportsService. Serves GET /reports
with spending-by-category breakdown, income vs expenses comparison, and
6-month bar chart history. First feature migrated to Django via Strangler Fig.
"""

from django.apps import AppConfig


class ReportsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "reports"
