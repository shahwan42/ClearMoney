"""
Installment URL patterns — routes for /installments*.

Static paths must come before UUID captures to avoid being swallowed.
"""

from django.urls import path

from installments import views

urlpatterns = [
    path("installments", views.installments_page, name="installments"),
    path("installments/add", views.installment_add, name="installment-add"),
    path(
        "installments/<uuid:id>/pay",
        views.installment_pay,
        name="installment-pay",
    ),
    path(
        "installments/<uuid:id>",
        views.installment_delete,
        name="installment-delete",
    ),
]
