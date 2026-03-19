"""
Salary wizard URL patterns — routes for /salary*.

All routes are static (no UUID captures), so ordering doesn't matter.
"""

from django.urls import path

from salary import views

urlpatterns = [
    path("salary", views.salary_page, name="salary"),
    path("salary/step2", views.salary_step2, name="salary-step2"),
    path("salary/step3", views.salary_step3, name="salary-step3"),
    path("salary/confirm", views.salary_confirm, name="salary-confirm"),
]
