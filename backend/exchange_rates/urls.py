"""
Exchange rate URL patterns — route for /exchange-rates.
"""

from django.urls import path

from exchange_rates import views

urlpatterns = [
    path("exchange-rates", views.exchange_rates_page, name="exchange-rates"),
]
