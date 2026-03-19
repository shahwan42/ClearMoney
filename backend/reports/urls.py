"""
Reports URL configuration.

Routes:
- /reports — monthly spending report with donut and bar charts
"""

from django.urls import path

from . import views

urlpatterns = [
    path('reports', views.reports_page, name='reports'),
]
