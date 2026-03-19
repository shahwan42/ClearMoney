"""
People URL patterns — page routes and JSON API.

Static paths come before UUID paths to avoid being swallowed
by the <uuid:person_id> converter.
"""

from django.urls import path

from people import views

urlpatterns = [
    # Page routes — static paths first
    path("people", views.people_page, name="people"),
    path("people/add", views.people_add, name="people-add"),
    path("people/<uuid:person_id>", views.person_detail, name="person-detail"),
    path("people/<uuid:person_id>/loan", views.people_loan, name="people-loan"),
    path("people/<uuid:person_id>/repay", views.people_repay, name="people-repay"),
    # JSON API routes
    path("api/persons", views.api_person_list_create, name="api-persons"),
    path("api/persons/<uuid:person_id>", views.api_person_detail, name="api-person-detail"),
    path("api/persons/<uuid:person_id>/loan", views.api_person_loan, name="api-person-loan"),
    path(
        "api/persons/<uuid:person_id>/repayment",
        views.api_person_repayment,
        name="api-person-repayment",
    ),
]
