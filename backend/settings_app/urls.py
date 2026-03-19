"""
Settings URL configuration.

Routes:
- /settings — settings page (dark mode, export, notifications, quick links)
- /export/transactions — CSV transaction export download
"""

from django.urls import path

from . import views

urlpatterns = [
    path('settings', views.settings_page, name='settings'),
    path('export/transactions', views.export_transactions, name='export-transactions'),
]
